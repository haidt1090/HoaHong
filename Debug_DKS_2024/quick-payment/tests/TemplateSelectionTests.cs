using System;
using System.IO;
using DKS.QuickPay;
static class TemplateSelectionTests
{
    public static void Run()
    {
        string folder = Path.Combine(Path.GetTempPath(), "DKS-template-tests-" + Guid.NewGuid().ToString("N"));
        string path = Path.Combine(folder, "printers.xml");
        try
        {
            var options = new PrinterOptions { HealthPrinter = "KSK A3", RecordPrinter = "Bệnh án A4" };
            options.SetTemplateSelected("ksk-adult", true); options.SaveTo(path);
            var restored = PrinterOptions.ReadFrom(path);
            if (!restored.IsTemplateSelected("ksk-adult")) throw new Exception("Selection not restored");
            restored.SetTemplateSelected("ksk-driver", true); restored.SaveTo(path);
            restored = PrinterOptions.ReadFrom(path);
            if (!restored.IsTemplateSelected("ksk-adult") || !restored.IsTemplateSelected("ksk-driver")) throw new Exception("Second selection cleared first");
            restored.SetTemplateSelected("ksk-adult", false); restored.SaveTo(path);
            restored = PrinterOptions.ReadFrom(path);
            if (restored.IsTemplateSelected("ksk-adult") || !restored.IsTemplateSelected("ksk-driver")) throw new Exception("Unchecked selection was not persisted");
            restored.HealthPrinter = "KSK khác"; restored.SaveTo(path);
            restored = PrinterOptions.ReadFrom(path);
            if (!restored.IsTemplateSelected("ksk-driver") || restored.RecordPrinter != "Bệnh án A4") throw new Exception("Changing printer lost selection");
            restored.SetTemplateSelected("ksk-driver", false); restored.SaveTo(path);
            if (PrinterOptions.ReadFrom(path).SelectedTemplateIds.Length != 0) throw new Exception("Unchecked-all wasn't preserved");
            // Existing users have a settings file with printers but no template list.
            File.WriteAllText(path, "<PrinterOptions><HealthPrinter>A3</HealthPrinter><RecordPrinter>A4</RecordPrinter></PrinterOptions>");
            restored = PrinterOptions.ReadFrom(path);
            if (restored.IsTemplateSelected("ksk-adult") || restored.HealthPrinter != "A3" || restored.RecordPrinter != "A4") throw new Exception("Old printer settings incompatible");
            Console.WriteLine("6 saved-template scenarios passed; selection is stored by template ID, not row position.");
        }
        finally { if (Directory.Exists(folder)) Directory.Delete(folder, true); }
    }
}
