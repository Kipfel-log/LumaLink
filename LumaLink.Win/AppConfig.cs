using System.Text.Json;
using System.Text.Json.Serialization;

namespace LumaLink;

/// <summary>应用配置（与 Python 版 config.json 字段完全兼容）。</summary>
public sealed class AppConfig
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private readonly object _lock = new();
    private readonly string _path;

    [JsonPropertyName("save_dir")] public string SaveDir { get; set; } =
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyPictures), "MobilePhotos");
    [JsonPropertyName("server_port")] public int ServerPort { get; set; } = 8989;
    [JsonPropertyName("preferred_ip")] public string PreferredIp { get; set; } = "";
    /// <summary>Auto / Light / Dark</summary>
    [JsonPropertyName("theme")] public string Theme { get; set; } = "Dark";
    [JsonPropertyName("background_image")] public string BackgroundImage { get; set; } = "kipfel_1.png";
    [JsonPropertyName("bg_opacity")] public int BgOpacity { get; set; } = 100;
    [JsonPropertyName("auto_copy_clipboard")] public bool AutoCopyClipboard { get; set; } = true;
    [JsonPropertyName("timeout_enabled")] public bool TimeoutEnabled { get; set; } = true;
    [JsonPropertyName("timeout_seconds")] public int TimeoutSeconds { get; set; } = 30;
    [JsonPropertyName("auto_rename_enabled")] public bool AutoRenameEnabled { get; set; } = true;
    [JsonPropertyName("name_prefix")] public string NamePrefix { get; set; } = "IMG_";
    [JsonPropertyName("start_index")] public int StartIndex { get; set; } = 1;
    [JsonPropertyName("current_index")] public int CurrentIndex { get; set; } = 1;
    [JsonPropertyName("digit_padding")] public int DigitPadding { get; set; } = 3;

    public AppConfig() : this(null) { }

    public AppConfig(string? path)
    {
        _path = path ?? ResolveDefaultPath();
    }

    /// <summary>优先使用 EXE 同级目录；目录不可写（如 Program Files）时回退到 LocalAppData。</summary>
    private static string ResolveDefaultPath()
    {
        var exeDir = AppContext.BaseDirectory;
        try
        {
            var probe = Path.Combine(exeDir, ".write_test");
            File.WriteAllText(probe, "");
            File.Delete(probe);
            return Path.Combine(exeDir, "config.json");
        }
        catch
        {
            var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LumaLink");
            Directory.CreateDirectory(dir);
            return Path.Combine(dir, "config.json");
        }
    }

    public static AppConfig Load(string? path = null)
    {
        var cfg = new AppConfig(path);
        lock (cfg._lock)
        {
            if (!File.Exists(cfg._path)) { cfg.SaveUnlocked(); return cfg; }
            try
            {
                var loaded = JsonSerializer.Deserialize<AppConfig>(File.ReadAllText(cfg._path), JsonOpts);
                if (loaded != null) cfg.CopyFrom(loaded);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[AppConfig] 加载失败，使用默认配置: {ex.Message}");
                cfg.SaveUnlocked();
            }
        }
        return cfg;
    }

    private void CopyFrom(AppConfig o)
    {
        SaveDir = string.IsNullOrWhiteSpace(o.SaveDir) ? SaveDir : o.SaveDir;
        ServerPort = o.ServerPort is >= 1 and <= 65535 ? o.ServerPort : ServerPort;
        PreferredIp = o.PreferredIp ?? "";
        Theme = o.Theme is "Auto" or "Light" or "Dark" ? o.Theme : "Dark";
        BackgroundImage = o.BackgroundImage ?? "None";
        BgOpacity = Math.Clamp(o.BgOpacity, 10, 100);
        AutoCopyClipboard = o.AutoCopyClipboard;
        TimeoutEnabled = o.TimeoutEnabled;
        TimeoutSeconds = Math.Clamp(o.TimeoutSeconds, 5, 3600);
        AutoRenameEnabled = o.AutoRenameEnabled;
        NamePrefix = o.NamePrefix ?? "IMG_";
        StartIndex = Math.Max(1, o.StartIndex);
        CurrentIndex = Math.Max(1, o.CurrentIndex);
        DigitPadding = Math.Clamp(o.DigitPadding, 1, 8);
    }

    private void SaveUnlocked()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            File.WriteAllText(_path, JsonSerializer.Serialize(this, JsonOpts));
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"[AppConfig] 保存失败: {ex.Message}");
        }
    }

    public void Save() { lock (_lock) SaveUnlocked(); }

    /// <summary>查看下一张文件名与序号（不递增）。</summary>
    public (string FileName, int Index) PeekNextFilename(string ext = ".jpg")
    {
        lock (_lock)
        {
            if (!AutoRenameEnabled) return ("IMG_YYYYMMDD_HHMMSS_001" + ext, CurrentIndex);
            return ($"{NamePrefix}{CurrentIndex.ToString().PadLeft(DigitPadding, '0')}{ext}", CurrentIndex);
        }
    }

    /// <summary>取当前文件名并将序号 +1 后持久化。</summary>
    public (string FileName, int Index) ConsumeNextFilename(string ext = ".jpg")
    {
        lock (_lock)
        {
            if (!ext.StartsWith('.')) ext = "." + ext;
            if (!AutoRenameEnabled)
                return ($"IMG_{DateTime.Now:yyyyMMdd_HHmmss}_001{ext}", CurrentIndex);
            var used = CurrentIndex;
            var name = $"{NamePrefix}{used.ToString().PadLeft(DigitPadding, '0')}{ext}";
            CurrentIndex++;
            SaveUnlocked();
            return (name, used);
        }
    }

    public void SetStartIndex(int index)
    {
        lock (_lock)
        {
            StartIndex = Math.Max(1, index);
            CurrentIndex = Math.Max(1, index);
            SaveUnlocked();
        }
    }
}
