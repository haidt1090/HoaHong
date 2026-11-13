using System;
using DKS.QuickPay;
static class ReportTests
{
    // Matches the real preview's setter-only public API and private backing field.
    class OriginalPreview
    {
        private object reportMain;
        public object MyReport { set { reportMain = value; } }
    }
    sealed class DerivedPreview : OriginalPreview { }
    public static void Run()
    {
        object report = new object();
        var preview = new OriginalPreview { MyReport = report };
        if (!ReferenceEquals(ReportAccess.FromPreview(preview), report)) throw new Exception("Wrong report");
        var derived = new DerivedPreview { MyReport = report };
        if (!ReferenceEquals(ReportAccess.FromPreview(derived), report)) throw new Exception("Wrong inherited report");
        try { ReportAccess.FromPreview(new OriginalPreview()); throw new Exception("Empty report accepted"); }
        catch (InvalidOperationException) { }
        Console.WriteLine("3 setter-only preview report scenarios passed; no Windows or printer run.");
    }
}
