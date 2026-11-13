using System;
using System.IO;
using System.Collections.Generic;
using System.Xml.Serialization;
namespace DKS.QuickPay
{
    public sealed class PrinterOptions
    {
        public string HealthPrinter { get; set; }
        public string RecordPrinter { get; set; }
        public string[] SelectedTemplateIds { get; set; } = new string[0];
        public bool IsTemplateSelected(string id)
        {
            return Array.IndexOf(SelectedTemplateIds ?? new string[0], id) >= 0;
        }
        public void SetTemplateSelected(string id, bool selected)
        {
            if (string.IsNullOrEmpty(id)) throw new ArgumentException("Mẫu không có mã để lưu lựa chọn.");
            var ids = new HashSet<string>(SelectedTemplateIds ?? new string[0], StringComparer.Ordinal);
            if (selected) ids.Add(id); else ids.Remove(id);
            SelectedTemplateIds = new string[ids.Count]; ids.CopyTo(SelectedTemplateIds);
            Array.Sort(SelectedTemplateIds, StringComparer.Ordinal);
        }
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
