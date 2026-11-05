using Microsoft.UI.Xaml.Media.Imaging;

namespace LumaLink;

public sealed class PhotoItem
{
    public required string Path { get; init; }
    public string Name => System.IO.Path.GetFileName(Path);
    public required string InfoText { get; init; }     // 时间/设备
    public required string DetailText { get; init; }   // 分辨率 | 大小
    public required BitmapImage Thumb { get; init; }
}
