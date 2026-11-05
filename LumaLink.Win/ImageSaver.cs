using Windows.Graphics.Imaging;
using Windows.Storage.Streams;

namespace LumaLink;

/// <summary>使用 Windows 原生 WIC (Windows.Graphics.Imaging) 解码、按 EXIF 校正方向并保存为 JPEG。</summary>
public static class ImageSaver
{
    public static async Task<(int Width, int Height)> SaveAsJpegAsync(byte[] data, string path, double quality = 0.95)
    {
        using var input = new InMemoryRandomAccessStream();
        using (var w = new DataWriter(input))
        {
            w.WriteBytes(data);
            await w.StoreAsync();
            w.DetachStream();
        }
        input.Seek(0);

        var decoder = await BitmapDecoder.CreateAsync(input);
        using var bitmap = await decoder.GetSoftwareBitmapAsync(
            BitmapPixelFormat.Bgra8,
            BitmapAlphaMode.Ignore,
            new BitmapTransform(),
            ExifOrientationMode.RespectExifOrientation,
            ColorManagementMode.DoNotColorManage);

        using var output = new InMemoryRandomAccessStream();
        var props = new BitmapPropertySet
        {
            { "ImageQuality", new BitmapTypedValue(quality, Windows.Foundation.PropertyType.Single) }
        };
        var encoder = await BitmapEncoder.CreateAsync(BitmapEncoder.JpegEncoderId, output, props);
        encoder.SetSoftwareBitmap(bitmap);
        await encoder.FlushAsync();

        output.Seek(0);
        var bytes = new byte[output.Size];
        using (var reader = new DataReader(output))
        {
            await reader.LoadAsync((uint)output.Size);
            reader.ReadBytes(bytes);
        }
        await File.WriteAllBytesAsync(path, bytes);
        return (bitmap.PixelWidth, bitmap.PixelHeight);
    }
}
