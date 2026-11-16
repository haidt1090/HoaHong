using System;
using DKS.QuickPay;
static class HealthLayoutTests
{
    public enum Paper { A4, A3 }
    public class Page { public Paper PaperKind { get; set; } public bool Landscape { get; set; } public int Margin { get; set; } = 17; }
    public class Section { public Page Page { get; set; } = new Page(); }
    public class Document { public Section[] Sections { get; set; } }
    public interface IDocument { Section[] Sections { get; } }
    public sealed class ExplicitDocument : IDocument
    {
        public Section Section = new Section();
        Section[] IDocument.Sections { get { return new[] { Section }; } }
    }
    public static void Run()
    {
        var doc = new Document { Sections = new[] { new Section(), new Section(), new Section() } };
        HealthPageLayout.Apply(doc);
        foreach (var section in doc.Sections) if (section.Page.PaperKind != Paper.A3 || !section.Page.Landscape || section.Page.Margin != 17) throw new Exception("Health layout didn't configure every section or changed margins");
        if (!HealthPageLayout.UseDuplex(true, true, false)) throw new Exception("Physical duplex disabled");
        if (HealthPageLayout.UseDuplex(true, false, true)) throw new Exception("PDF required physical duplex");
        foreach (var capabilities in new[] { new[] {false,true,false}, new[] {true,false,false}, new[] {false,false,true} })
        {
            try { HealthPageLayout.UseDuplex(capabilities[0],capabilities[1],capabilities[2]); throw new Exception("Unsupported print capabilities accepted"); }
            catch (InvalidOperationException) { }
        }
        var explicitDoc = new ExplicitDocument(); HealthPageLayout.Apply(explicitDoc);
        if (explicitDoc.Section.Page.PaperKind != Paper.A3 || !explicitDoc.Section.Page.Landscape) throw new Exception("Explicit document API not configured");
        Console.WriteLine("7 A3 landscape and duplex-policy scenarios passed; physical driver/printing not tested.");
    }
}
