using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace LumaLink;

public sealed class DeviceInfo
{
    public string Ua { get; init; } = "";
    public DateTime LastHeartbeat { get; set; } = DateTime.UtcNow;
}

/// <summary>
/// 嵌入式手机采集 HTTP 服务（基于 TcpListener 自实现的最小 HTTP/1.1，
/// 无需管理员权限 / URL ACL，监听 0.0.0.0 全网卡）。
/// </summary>
public sealed class MobileServer : IDisposable
{
    private readonly AppConfig _cfg;
    private readonly object _lock = new();
    private readonly Dictionary<string, DeviceInfo> _devices = new();
    private TcpListener? _listener;
    private CancellationTokenSource? _cts;
    private readonly string _html;

    public string PinCode { get; private set; } = "";
    public int Port { get; private set; }
    public string CurrentIp { get; set; } = "127.0.0.1";
    public string SaveDir { get; set; }
    public bool IsRunning { get; private set; }
    public int ActiveDeviceCount { get { lock (_lock) return _devices.Count; } }

    /// <summary>(文件路径, 宽, 高, 信息串) —— 在后台线程触发。</summary>
    public event Action<string, int, int, string>? PhotoSaved;
    public event Action<string>? ClientConnected;     // 设备显示名
    public event Action<string>? ClientDisconnected;
    public event Action<string, int>? NextSeqChanged; // 下一文件名, 序号

    public MobileServer(AppConfig cfg, string saveDir)
    {
        _cfg = cfg;
        SaveDir = saveDir;
        Port = cfg.ServerPort;
        GeneratePin();
        using var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("mobile.html")
                      ?? throw new InvalidOperationException("缺少内嵌资源 mobile.html");
        using var r = new StreamReader(s, Encoding.UTF8);
        _html = r.ReadToEnd();
    }

    public string GeneratePin() => PinCode = RandomNumberGenerator.GetInt32(100000, 1000000).ToString();

    public (string, int) GetNextPhotoInfo() => _cfg.PeekNextFilename(".jpg");

    // ───────── 生命周期 ─────────
    public (bool Ok, string Message) Start(int? port = null)
    {
        if (port.HasValue) Port = port.Value;
        var ips = NetworkUtil.GetAllLanIps();
        if (string.IsNullOrEmpty(CurrentIp) || !ips.Any(i => i.Ip == CurrentIp)) CurrentIp = ips[0].Ip;
        if (IsRunning) return (true, $"http://{CurrentIp}:{Port}");

        try
        {
            _listener = new TcpListener(IPAddress.Any, Port);
            _listener.Start();
            _cts = new CancellationTokenSource();
            IsRunning = true;
            _ = Task.Run(() => AcceptLoop(_listener, _cts.Token));
            _ = Task.Run(() => TimeoutLoop(_cts.Token));
            return (true, $"http://{CurrentIp}:{Port}");
        }
        catch (Exception ex)
        {
            IsRunning = false;
            return (false, $"绑定端口 {Port} 失败: {ex.Message}");
        }
    }

    public (bool Ok, string Message) Restart(int? port = null)
    {
        Stop();
        return Start(port);
    }

    public void Stop()
    {
        IsRunning = false;
        try { _cts?.Cancel(); } catch { }
        try { _listener?.Stop(); } catch { }
        _listener = null;
    }

    public void Dispose() => Stop();

    // ───────── 设备管理 ─────────
    private static string ShortName(string ua) =>
        ua.Contains("iPhone") || ua.Contains("iPad") ? "iOS" : ua.Contains("Android") ? "Android" : "Mobile";

    private async Task TimeoutLoop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try { await Task.Delay(3000, ct); } catch { return; }
            if (!_cfg.TimeoutEnabled) continue;
            var limit = TimeSpan.FromSeconds(_cfg.TimeoutSeconds);
            var now = DateTime.UtcNow;
            var gone = new List<string>();
            lock (_lock)
            {
                foreach (var (tok, info) in _devices.ToList())
                {
                    if (now - info.LastHeartbeat > limit)
                    {
                        gone.Add(ShortName(info.Ua) + " 客户端");
                        _devices.Remove(tok);
                    }
                }
            }
            foreach (var name in gone) ClientDisconnected?.Invoke(name);
        }
    }

    // ───────── HTTP ─────────
    private async Task AcceptLoop(TcpListener listener, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            TcpClient client;
            try { client = await listener.AcceptTcpClientAsync(ct); }
            catch { return; }
            _ = Task.Run(() => HandleClient(client, ct));
        }
    }

    private const int MaxBody = 64 * 1024 * 1024;

    private async Task HandleClient(TcpClient client, CancellationToken ct)
    {
        using (client)
        {
            try
            {
                client.ReceiveTimeout = client.SendTimeout = 30000;
                using var stream = client.GetStream();
                var (method, path, body) = await ReadRequest(stream, ct);
                if (method == null) return;

                if (method == "GET" && (path == "/" || path.StartsWith("/?")))
                {
                    await WriteResponse(stream, 200, "text/html; charset=utf-8", Encoding.UTF8.GetBytes(_html));
                }
                else if (method == "POST" && path.StartsWith("/api/"))
                {
                    JsonObject result;
                    try { result = await HandleApi(path, Encoding.UTF8.GetString(body)); }
                    catch (Exception ex) { result = new JsonObject { ["ok"] = false, ["error"] = ex.Message }; }
                    await WriteResponse(stream, 200, "application/json", Encoding.UTF8.GetBytes(result.ToJsonString(
                        new JsonSerializerOptions { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping })));
                }
                else
                {
                    await WriteResponse(stream, 404, "text/plain; charset=utf-8", Encoding.UTF8.GetBytes("404 Not Found"));
                }
            }
            catch { /* 客户端断开等，忽略 */ }
        }
    }

    private static async Task<(string? Method, string Path, byte[] Body)> ReadRequest(NetworkStream stream, CancellationToken ct)
    {
        var buf = new List<byte>(4096);
        var tmp = new byte[8192];
        int headerEnd = -1;
        while (headerEnd < 0)
        {
            int n = await stream.ReadAsync(tmp, ct);
            if (n == 0) return (null, "", Array.Empty<byte>());
            buf.AddRange(tmp.AsSpan(0, n).ToArray());
            headerEnd = IndexOfHeaderEnd(buf);
            if (buf.Count > 64 * 1024 && headerEnd < 0) return (null, "", Array.Empty<byte>());
        }

        var head = Encoding.ASCII.GetString(buf.GetRange(0, headerEnd).ToArray());
        var lines = head.Split("\r\n");
        var parts = lines[0].Split(' ');
        if (parts.Length < 2) return (null, "", Array.Empty<byte>());

        int contentLength = 0;
        foreach (var line in lines.Skip(1))
        {
            var idx = line.IndexOf(':');
            if (idx > 0 && line[..idx].Trim().Equals("Content-Length", StringComparison.OrdinalIgnoreCase))
                int.TryParse(line[(idx + 1)..].Trim(), out contentLength);
        }
        if (contentLength < 0 || contentLength > MaxBody) return (null, "", Array.Empty<byte>());

        var body = new byte[contentLength];
        int have = Math.Min(contentLength, buf.Count - (headerEnd + 4));
        if (have > 0) buf.CopyTo(headerEnd + 4, body, 0, have);
        while (have < contentLength)
        {
            int n = await stream.ReadAsync(body.AsMemory(have, contentLength - have), ct);
            if (n == 0) break;
            have += n;
        }
        return (parts[0], parts[1], body);
    }

    private static int IndexOfHeaderEnd(List<byte> b)
    {
        for (int i = 0; i + 3 < b.Count; i++)
            if (b[i] == 13 && b[i + 1] == 10 && b[i + 2] == 13 && b[i + 3] == 10) return i;
        return -1;
    }

    private static async Task WriteResponse(NetworkStream s, int code, string type, byte[] body)
    {
        var reason = code == 200 ? "OK" : "Not Found";
        var head = $"HTTP/1.1 {code} {reason}\r\nContent-Type: {type}\r\nContent-Length: {body.Length}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
        await s.WriteAsync(Encoding.ASCII.GetBytes(head));
        await s.WriteAsync(body);
        await s.FlushAsync();
    }

    // ───────── API ─────────
    private async Task<JsonObject> HandleApi(string path, string bodyText)
    {
        var data = JsonNode.Parse(bodyText) as JsonObject ?? new JsonObject();
        string Str(string k) => data[k]?.GetValue<string>() ?? "";

        switch (path)
        {
            case "/api/verify":
            {
                if (Str("pin").Trim() != PinCode)
                    return Err("验证码错误，请核对电脑屏幕上的 6 位数字");
                var token = "tok_" + RandomNumberGenerator.GetInt32(100000, 1000000);
                var ua = Str("ua"); if (ua == "") ua = "Mobile Device";
                lock (_lock) _devices[token] = new DeviceInfo { Ua = ua };
                ClientConnected?.Invoke(ShortName(ua) + " 客户端");
                var (fn, sq) = GetNextPhotoInfo();
                return new JsonObject { ["ok"] = true, ["token"] = token, ["next_filename"] = fn, ["next_seq"] = sq };
            }
            case "/api/heartbeat":
            {
                if (!Touch(Str("token"))) return Err("无效的会话");
                var (fn, sq) = GetNextPhotoInfo();
                return new JsonObject { ["ok"] = true, ["next_filename"] = fn, ["next_seq"] = sq };
            }
            case "/api/upload":
            {
                var token = Str("token");
                if (!Touch(token)) return Err("无效的或已超时的会话，请重新连接");
                var dataUrl = Str("image");
                var comma = dataUrl.IndexOf(',');
                if (comma < 0) return Err("无效的图片数据");
                byte[] img = Convert.FromBase64String(dataUrl[(comma + 1)..]);

                string ua; lock (_lock) ua = _devices.TryGetValue(token, out var d) ? d.Ua : "";
                var info = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} ({ShortName(ua)})";

                var file = GenerateSavePath();
                int w, h;
                try { (w, h) = await ImageSaver.SaveAsJpegAsync(img, file); }
                catch { return Err("解析图片失败"); }

                var (nfn, nsq) = GetNextPhotoInfo();
                PhotoSaved?.Invoke(file, w, h, info);
                NextSeqChanged?.Invoke(nfn, nsq);
                return new JsonObject
                {
                    ["ok"] = true, ["filename"] = Path.GetFileName(file),
                    ["next_filename"] = nfn, ["next_seq"] = nsq
                };
            }
            default:
                return Err("未知接口");
        }
    }

    private static JsonObject Err(string m) => new() { ["ok"] = false, ["error"] = m };

    private bool Touch(string token)
    {
        lock (_lock)
        {
            if (!_devices.TryGetValue(token, out var d)) return false;
            d.LastHeartbeat = DateTime.UtcNow;
            return true;
        }
    }

    private string GenerateSavePath()
    {
        Directory.CreateDirectory(SaveDir);
        if (_cfg.AutoRenameEnabled)
        {
            var (name, _) = _cfg.ConsumeNextFilename(".jpg");
            var p = Path.Combine(SaveDir, name);
            while (File.Exists(p)) { (name, _) = _cfg.ConsumeNextFilename(".jpg"); p = Path.Combine(SaveDir, name); }
            return p;
        }
        var stem = $"IMG_{DateTime.Now:yyyyMMdd_HHmmss}";
        int c = 1;
        var path = Path.Combine(SaveDir, $"{stem}_{c:000}.jpg");
        while (File.Exists(path)) path = Path.Combine(SaveDir, $"{stem}_{++c:000}.jpg");
        return path;
    }
}
