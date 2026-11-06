using Microsoft.UI.Xaml.Media.Imaging;

namespace LumaLink;

public sealed class PhotoItem
{
    public string Path { get; set; } = string.Empty;
    public string Name => System.IO.Path.GetFileName(Path);
    public string InfoText { get; set; } = string.Empty;     // 时间/设备
    public string DetailText { get; set; } = string.Empty;   // 分辨率 | 大小
    public BitmapImage Thumb { get; set; } = new();
}
