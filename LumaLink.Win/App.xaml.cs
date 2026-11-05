using System.Runtime.InteropServices;
using Microsoft.UI.Xaml;

namespace LumaLink;

public partial class App : Application
{
    private Window? _window;

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SetCurrentProcessExplicitAppUserModelID(string appId);

    public App()
    {
        try { SetCurrentProcessExplicitAppUserModelID("KipfelLog.LumaLink.v2"); } catch { }
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        _window = new MainWindow();
        _window.Activate();
    }
}
