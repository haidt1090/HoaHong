using System;
using System.IO;
using System.Xml.Serialization;
namespace DKS.QuickPay
{
    public sealed class PrinterOptions
    {
        public string HealthPrinter { get; set; }
        public string RecordPrinter { get; set; }
        static string FilePath { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DakhoasoSoft", "printer-settings.xml"); } }
        public static PrinterOptions Read() { return ReadFrom(FilePath); }
        internal static PrinterOptions ReadFrom(string path)
        {
            if (!File.Exists(path)) return new PrinterOptions();
            using (var stream = File.OpenRead(path)) return (PrinterOptions)new XmlSerializer(typeof(PrinterOptions)).Deserialize(stream);
        }
        public void Save() { SaveTo(FilePath); }
        internal void SaveTo(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var stream = File.Create(temp)) new XmlSerializer(typeof(PrinterOptions)).Serialize(stream, this);
                if (File.Exists(path)) File.Replace(temp, path, null); else File.Move(temp, path);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        }
    }
}
