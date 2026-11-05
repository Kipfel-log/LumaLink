using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.WindowsRuntime;
using Microsoft.UI;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using QRCoder;
using Windows.ApplicationModel.DataTransfer;
using Windows.Graphics;
using Windows.Storage;
using Windows.Storage.Pickers;
using Windows.Storage.Streams;
using WinRT.Interop;

namespace LumaLink;

public sealed partial class MainWindow : Window
{
    [DllImport("user32.dll")] private static extern uint GetDpiForWindow(IntPtr hwnd);

    private readonly AppConfig _cfg;
    private readonly MobileServer _server;
    private readonly DispatcherQueue _ui;
    public ObservableCollection<PhotoItem> Photos { get; } = new();

    private string _saveDir;
    private int _received;
    private bool _loading = true;

    public MainWindow()
    {
        _cfg = AppConfig.Load();
        _ui = DispatcherQueue.GetForCurrentThread();
        _saveDir = Path.GetFullPath(_cfg.SaveDir);
        Directory.CreateDirectory(_saveDir);

        InitializeComponent();

        // 窗口图标 / 尺寸 / Mica 云母
        SystemBackdrop = new MicaBackdrop();
        var hwnd = WindowNative.GetWindowHandle(this);
        var scale = GetDpiForWindow(hwnd) / 96.0;
        AppWindow.Resize(new SizeInt32((int)(1180 * scale), (int)(760 * scale)));
        var ico = AssetPath("lumalink_icon_mark.ico");
        if (File.Exists(ico)) AppWindow.SetIcon(ico);

        var logo = AssetPath("lumalink_full_lockup.png");
        if (File.Exists(logo)) LogoImage.Source = new BitmapImage(new Uri(logo));

        // 载入配置到设置控件
        PathBox.Text = _saveDir;
        ClipboardSwitch.IsOn = _cfg.AutoCopyClipboard;
        TimeoutSwitch.IsOn = _cfg.TimeoutEnabled;
        TimeoutBox.Value = _cfg.TimeoutSeconds;
        TimeoutBox.IsEnabled = _cfg.TimeoutEnabled;
        RenameSwitch.IsOn = _cfg.AutoRenameEnabled;
        PrefixBox.Text = _cfg.NamePrefix;
        SeqBox.Value = _cfg.CurrentIndex;
        DigitBox.Value = _cfg.DigitPadding;
        PortBox.Value = _cfg.ServerPort;
        OpacitySlider.Value = _cfg.BgOpacity;
        OpacityText.Text = $"{_cfg.BgOpacity}%";
        ThemeCombo.SelectedIndex = _cfg.Theme switch { "Auto" => 0, "Light" => 1, _ => 2 };
        ApplyRenameEnabledState();
        PopulateBackgrounds();
        ApplyTheme();
        ApplyBackground();
        RootGrid.ActualThemeChanged += (_, _) => UpdateMask();

        _server = new MobileServer(_cfg, _saveDir);
        _server.PhotoSaved += (p, w, h, info) => _ui.TryEnqueue(() => OnPhotoSaved(p, w, h, info));
        _server.ClientConnected += n => _ui.TryEnqueue(() => OnClientConnected(n));
        _server.ClientDisconnected += n => _ui.TryEnqueue(() => UpdateClientCount());
        _server.NextSeqChanged += (fn, sq) => _ui.TryEnqueue(() => OnNextSeqChanged(sq));

        Nav.SelectedItem = HomeItem;
        _loading = false;

        StartServer();
        UpdateNextSeqDisplay();
        Closed += (_, _) => { _cfg.Save(); _server.Stop(); };
    }

    private static string AssetPath(string name) => Path.Combine(AppContext.BaseDirectory, "Assets", name);
    private static string BackgroundDir => Path.Combine(AppContext.BaseDirectory, "Assets", "background");

    // ───────── 导航 ─────────
    private void Nav_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItem as NavigationViewItem)?.Tag as string;
        HomePanel.Visibility = tag == "settings" ? Visibility.Collapsed : Visibility.Visible;
        SettingsPanel.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }

    // ───────── 通知 ─────────
    private void Notify(InfoBarSeverity severity, string title, string message, int ms = 3000)
    {
        var bar = new InfoBar { Severity = severity, Title = title, Message = message, IsOpen = true, IsClosable = true };
        InfoHost.Children.Insert(0, bar);
        var timer = _ui.CreateTimer();
        timer.Interval = TimeSpan.FromMilliseconds(ms);
        timer.IsRepeating = false;
        timer.Tick += (_, _) => InfoHost.Children.Remove(bar);
        bar.Closed += (_, _) => { timer.Stop(); InfoHost.Children.Remove(bar); };
        timer.Start();
    }

    // ───────── 服务器 / 二维码 ─────────
    private void StartServer()
    {
        var (ok, msg) = _server.Start(_cfg.ServerPort);
        PopulateNetworkCards();
        if (!ok)
        {
            StatusText.Text = "服务器启动失败";
            Notify(InfoBarSeverity.Error, "服务器启动失败", msg, 5000);
            return;
        }
        var target = string.IsNullOrEmpty(_cfg.PreferredIp) ? _server.CurrentIp : _cfg.PreferredIp;
        var idx = 0;
        for (int i = 0; i < NetCombo.Items.Count; i++)
            if ((NetCombo.Items[i] as ComboBoxItem)?.Tag as string == target) { idx = i; break; }
        _loading = true;
        NetCombo.SelectedIndex = idx;
        _loading = false;
        var ip = (NetCombo.Items[idx] as ComboBoxItem)?.Tag as string ?? target;
        _server.CurrentIp = ip;
        UpdateQrAndUrl(ip);
        PinText.Text = _server.PinCode;
    }

    private void PopulateNetworkCards()
    {
        _loading = true;
        NetCombo.Items.Clear();
        foreach (var (ip, label) in NetworkUtil.GetAllLanIps())
            NetCombo.Items.Add(new ComboBoxItem { Content = label, Tag = ip });
        _loading = false;
    }

    private async void UpdateQrAndUrl(string ip)
    {
        var url = $"http://{ip}:{_server.Port}";
        UrlText.Text = url;
        StatusText.Text = "服务运行中";
        try
        {
            using var gen = new QRCodeGenerator();
            using var data = gen.CreateQrCode(url, QRCodeGenerator.ECCLevel.M);
            var png = new PngByteQRCode(data).GetGraphic(10);
            var bmp = new BitmapImage();
            using var ms = new InMemoryRandomAccessStream();
            await ms.WriteAsync(png.AsBuffer());
            ms.Seek(0);
            await bmp.SetSourceAsync(ms);
            QrImage.Source = bmp;
        }
        catch (Exception ex) { Debug.WriteLine($"二维码生成错误: {ex.Message}"); }
    }

    private void RefreshPin_Click(object sender, RoutedEventArgs e)
    {
        PinText.Text = _server.GeneratePin();
        Notify(InfoBarSeverity.Success, "验证码已重置", $"最新配对验证码: {_server.PinCode}", 2000);
    }

    private void ApplyPort_Click(object sender, RoutedEventArgs e)
    {
        var port = (int)PortBox.Value;
        var ip = (NetCombo.SelectedItem as ComboBoxItem)?.Tag as string;
        _cfg.ServerPort = port;
        if (!string.IsNullOrEmpty(ip)) { _cfg.PreferredIp = ip; _server.CurrentIp = ip; }
        _cfg.Save();
        var (ok, msg) = _server.Restart(port);
        if (ok)
        {
            UpdateQrAndUrl(_server.CurrentIp);
            Notify(InfoBarSeverity.Success, "网络通信设置已更新", $"已成功绑定端口 {port}，访问地址: http://{_server.CurrentIp}:{port}", 3500);
        }
        else
        {
            StatusText.Text = "端口绑定失败";
            Notify(InfoBarSeverity.Error, "端口重启失败", msg, 4000);
        }
    }

    private void NetCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_loading || NetCombo.SelectedItem is not ComboBoxItem item || item.Tag is not string ip) return;
        _cfg.PreferredIp = ip;
        _cfg.Save();
        _server.CurrentIp = ip;
        UpdateQrAndUrl(ip);
        Notify(InfoBarSeverity.Informational, "通信网卡/IP 已切换并保存", $"手机访问 IP 已切换为: {ip}");
    }

    // ───────── 设备 / 照片事件 ─────────
    private void OnClientConnected(string name)
    {
        UpdateClientCount(name);
        Notify(InfoBarSeverity.Informational, "手机设备已连接", $"{name} 通过验证码配对成功");
    }

    private void UpdateClientCount(string? name = null) =>
        ClientText.Text = $"已连接设备: {_server.ActiveDeviceCount} 台" + (name != null ? $" ({name})" : "");

    private void OnNextSeqChanged(int seq)
    {
        _loading = true;
        SeqBox.Value = seq;
        _loading = false;
        UpdateNextSeqDisplay();
    }

    private async void OnPhotoSaved(string path, int w, int h, string info)
    {
        _received++;
        var full = new BitmapImage { DecodePixelWidth = 1600 };
        full.UriSource = new Uri(path);
        PreviewImage.Source = full;
        PreviewHint.Visibility = Visibility.Collapsed;
        CountText.Text = $"本次启动已接收: {_received} 张照片";

        var bytes = new FileInfo(path).Length;
        var size = bytes >= 1024 * 1024 ? $"{bytes / 1048576.0:F2} MB" : $"{bytes / 1024.0:F1} KB";
        var thumb = new BitmapImage { DecodePixelWidth = 200 };
        thumb.UriSource = new Uri(path);
        Photos.Insert(0, new PhotoItem
        {
            Path = path,
            InfoText = $"时间/设备: {info}",
            DetailText = $"分辨率: {w} × {h} | 大小: {size}",
            Thumb = thumb,
        });
        PhotoList.SelectedIndex = 0;
        UpdateListUi();

        var copied = "";
        if (_cfg.AutoCopyClipboard && await CopyToClipboard(path)) copied = "，并已自动复制到剪贴板";
        Notify(InfoBarSeverity.Success, "手机拍照保存成功", $"图片已保存为 {Path.GetFileName(path)}{copied}", 3500);
    }

    private static async Task<bool> CopyToClipboard(string path)
    {
        try
        {
            var file = await StorageFile.GetFileFromPathAsync(path);
            var pkg = new DataPackage();
            pkg.SetBitmap(RandomAccessStreamReference.CreateFromFile(file));
            Clipboard.SetContent(pkg);
            Clipboard.Flush();
            return true;
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"[Clipboard] 复制失败: {ex.Message}");
            return false;
        }
    }

    private void UpdateListUi()
    {
        HistoryTitle.Text = $"已保存照片历史 ({Photos.Count} 张)";
        ClearBtn.IsEnabled = Photos.Count > 0;
    }

    private static PhotoItem? ItemOf(object sender) => (sender as FrameworkElement)?.DataContext as PhotoItem;

    private async void CopyPhoto_Click(object sender, RoutedEventArgs e)
    {
        if (ItemOf(sender) is { } item && await CopyToClipboard(item.Path))
            Notify(InfoBarSeverity.Success, "已复制到剪贴板", $"照片 {item.Name} 已写入系统剪贴板", 2500);
    }

    private void LocatePhoto_Click(object sender, RoutedEventArgs e)
    {
        if (ItemOf(sender) is { } item && File.Exists(item.Path))
            Process.Start("explorer.exe", $"/select,\"{item.Path}\"");
    }

    private void OpenPhoto_Click(object sender, RoutedEventArgs e)
    {
        if (ItemOf(sender) is { } item) OpenWithShell(item.Path);
    }

    private void PhotoList_DoubleTapped(object sender, DoubleTappedRoutedEventArgs e)
    {
        if (PhotoList.SelectedItem is PhotoItem item) OpenWithShell(item.Path);
    }

    private static void OpenWithShell(string path)
    {
        if (!File.Exists(path) && !Directory.Exists(path)) return;
        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
    }

    private void DeletePhoto_Click(object sender, RoutedEventArgs e)
    {
        if (ItemOf(sender) is not { } item) return;
        try { if (File.Exists(item.Path)) File.Delete(item.Path); }
        catch (Exception ex) { Notify(InfoBarSeverity.Error, "文件删除失败", ex.Message); return; }
        Photos.Remove(item);
        UpdateListUi();
        Notify(InfoBarSeverity.Informational, "照片已彻底删除", $"从磁盘移除了文件: {item.Name}");
    }

    private void Clear_Click(object sender, RoutedEventArgs e)
    {
        Photos.Clear();
        UpdateListUi();
    }

    // ───────── 设置：目录 ─────────
    private async void BrowseDir_Click(object sender, RoutedEventArgs e)
    {
        var picker = new FolderPicker { SuggestedStartLocation = PickerLocationId.PicturesLibrary };
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var folder = await picker.PickSingleFolderAsync();
        if (folder == null) return;
        _saveDir = folder.Path;
        Directory.CreateDirectory(_saveDir);
        _cfg.SaveDir = _saveDir;
        _cfg.Save();
        _server.SaveDir = _saveDir;
        PathBox.Text = _saveDir;
        Notify(InfoBarSeverity.Success, "保存目录已更改并保存", $"后续拍摄的照片将存入: {_saveDir}", 3500);
    }

    private void OpenDir_Click(object sender, RoutedEventArgs e) => OpenWithShell(_saveDir);

    // ───────── 设置：开关与数值 ─────────
    private void ClipboardSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        _cfg.AutoCopyClipboard = ClipboardSwitch.IsOn;
        _cfg.Save();
    }

    private void TimeoutSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        _cfg.TimeoutEnabled = TimeoutSwitch.IsOn;
        _cfg.Save();
        TimeoutBox.IsEnabled = TimeoutSwitch.IsOn;
    }

    private void TimeoutBox_ValueChanged(NumberBox sender, NumberBoxValueChangedEventArgs args)
    {
        if (_loading || double.IsNaN(sender.Value)) return;
        _cfg.TimeoutSeconds = (int)sender.Value;
        _cfg.Save();
    }

    private void RenameSwitch_Toggled(object sender, RoutedEventArgs e)
    {
        if (_loading) return;
        _cfg.AutoRenameEnabled = RenameSwitch.IsOn;
        _cfg.Save();
        ApplyRenameEnabledState();
        UpdateNextSeqDisplay();
    }

    private void ApplyRenameEnabledState()
    {
        var on = RenameSwitch.IsOn;
        PrefixBox.IsEnabled = SeqBox.IsEnabled = DigitBox.IsEnabled = on;
    }

    private void PrefixBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (_loading) return;
        _cfg.NamePrefix = PrefixBox.Text.Trim();
        _cfg.Save();
        UpdateNextSeqDisplay();
    }

    private void SeqBox_ValueChanged(NumberBox sender, NumberBoxValueChangedEventArgs args)
    {
        if (_loading || double.IsNaN(sender.Value)) return;
        _cfg.SetStartIndex((int)sender.Value);
        UpdateNextSeqDisplay();
    }

    private void DigitBox_ValueChanged(NumberBox sender, NumberBoxValueChangedEventArgs args)
    {
        if (_loading || double.IsNaN(sender.Value)) return;
        _cfg.DigitPadding = (int)sender.Value;
        _cfg.Save();
        UpdateNextSeqDisplay();
    }

    private void UpdateNextSeqDisplay()
    {
        var (fn, seq) = _cfg.PeekNextFilename(".jpg");
        if (_cfg.AutoRenameEnabled)
        {
            NextSeqText.Text = $"下一张照片: #{seq.ToString().PadLeft(_cfg.DigitPadding, '0')} ({fn})";
            RenamePreviewText.Text = $"格式生效示例: {fn}";
        }
        else
        {
            NextSeqText.Text = "下一张照片: 原始时间戳自动命名";
            RenamePreviewText.Text = "自动重命名已禁用 (使用时间戳)";
        }
    }

    // ───────── 设置：主题 / 背景 ─────────
    private void ThemeCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_loading || ThemeCombo.SelectedItem is not ComboBoxItem item) return;
        _cfg.Theme = (string)item.Tag;
        _cfg.Save();
        ApplyTheme();
    }

    private void ApplyTheme()
    {
        RootGrid.RequestedTheme = _cfg.Theme switch
        {
            "Light" => ElementTheme.Light,
            "Dark" => ElementTheme.Dark,
            _ => ElementTheme.Default,
        };
        UpdateMask();
    }

    private void PopulateBackgrounds()
    {
        var wasLoading = _loading;
        _loading = true;
        BgCombo.Items.Clear();
        BgCombo.Items.Add(new ComboBoxItem { Content = "默认无背景", Tag = "None" });
        int sel = 0, i = 1;
        if (Directory.Exists(BackgroundDir))
        {
            var exts = new[] { ".png", ".jpg", ".jpeg", ".webp", ".bmp" };
            foreach (var f in Directory.GetFiles(BackgroundDir).OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
            {
                if (!exts.Contains(Path.GetExtension(f).ToLowerInvariant())) continue;
                var name = Path.GetFileName(f);
                BgCombo.Items.Add(new ComboBoxItem { Content = name, Tag = name });
                if (name == _cfg.BackgroundImage) sel = i;
                i++;
            }
        }
        BgCombo.SelectedIndex = sel;
        _loading = wasLoading;
    }

    private void RefreshBg_Click(object sender, RoutedEventArgs e) => PopulateBackgrounds();

    private void BgCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_loading || BgCombo.SelectedItem is not ComboBoxItem item) return;
        _cfg.BackgroundImage = (string)item.Tag;
        _cfg.Save();
        ApplyBackground();
        Notify(InfoBarSeverity.Success, "背景图片已更新",
            $"已生效背景设置: {(_cfg.BackgroundImage == "None" ? "默认无背景" : _cfg.BackgroundImage)}", 2500);
    }

    private void OpacitySlider_ValueChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        if (_loading) return;
        var v = (int)e.NewValue;
        OpacityText.Text = $"{v}%";
        _cfg.BgOpacity = v;
        _cfg.Save();
        ApplyBackground();
    }

    private void ApplyBackground()
    {
        var name = _cfg.BackgroundImage;
        var path = string.IsNullOrEmpty(name) || name == "None" ? null : Path.Combine(BackgroundDir, name);
        if (path != null && File.Exists(path))
        {
            BgImage.Source = new BitmapImage(new Uri(path));
            BgImage.Opacity = _cfg.BgOpacity / 100.0;
            BgImage.Visibility = BgMask.Visibility = Visibility.Visible;
        }
        else
        {
            BgImage.Source = null;
            BgImage.Visibility = BgMask.Visibility = Visibility.Collapsed;
        }
        UpdateMask();
    }

    /// <summary>背景图之上的读写保护遮罩，随深浅色主题与透明度变化。</summary>
    private void UpdateMask()
    {
        var op = _cfg.BgOpacity / 100.0;
        var alpha = (byte)(140 * (1.0 - op * 0.3));
        var dark = RootGrid.ActualTheme == ElementTheme.Dark;
        BgMask.Fill = new SolidColorBrush(dark
            ? Windows.UI.Color.FromArgb(alpha, 20, 20, 20)
            : Windows.UI.Color.FromArgb(alpha, 245, 245, 245));
    }
}
