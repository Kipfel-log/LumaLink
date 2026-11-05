using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace LumaLink;

public static class NetworkUtil
{
    private static readonly string[] VirtualKeywords =
        { "vmware", "virtualbox", "vbox", "hyper-v", "wsl", "vethernet" };

    /// <summary>返回所有局域网 IPv4 及显示名称。</summary>
    public static List<(string Ip, string Label)> GetAllLanIps()
    {
        var res = new List<(string, string)>();
        var seen = new HashSet<string>();

        // 1. UDP 外连探测主路由网卡（不会真正发包）
        try
        {
            using var s = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            s.Connect(IPAddress.Parse("114.114.114.114"), 80);
            var ip = ((IPEndPoint)s.LocalEndPoint!).Address.ToString();
            if (!ip.StartsWith("127.") && seen.Add(ip)) res.Add((ip, $"{ip} (主物理网卡)"));
        }
        catch { }

        // 2. 遍历其余网卡（Wi-Fi / 热点等）
        try
        {
            foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (nic.OperationalStatus != OperationalStatus.Up) continue;
                if (nic.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;
                var lower = nic.Name.ToLowerInvariant() + " " + nic.Description.ToLowerInvariant();
                if (VirtualKeywords.Any(lower.Contains)) continue;
                foreach (var ua in nic.GetIPProperties().UnicastAddresses)
                {
                    if (ua.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                    var ip = ua.Address.ToString();
                    if (ip.StartsWith("127.") || ip.StartsWith("169.254.")) continue;
                    if (seen.Add(ip)) res.Add((ip, $"{ip} ({nic.Name})"));
                }
            }
        }
        catch { }

        if (res.Count == 0) res.Add(("127.0.0.1", "127.0.0.1 (本地回环)"));
        return res;
    }
}
