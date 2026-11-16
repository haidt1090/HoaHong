using System;
using System.Collections;
using System.Reflection;
namespace DKS.QuickPay
{
    public static class HealthPageLayout
    {
        static PropertyInfo Member(object value, string name)
        {
            var property = value.GetType().GetProperty(name);
            if (property != null) return property;
            foreach (Type contract in value.GetType().GetInterfaces())
            {
                property = contract.GetProperty(name);
                if (property != null) return property;
            }
            throw new MissingMemberException(value.GetType().FullName, name);
        }
        public static void Apply(object document)
        {
            if (document == null) throw new ArgumentNullException("document");
            var sections = (IEnumerable)Member(document, "Sections").GetValue(document, null);
            int count = 0;
            foreach (object section in sections)
            {
                object page = Member(section, "Page").GetValue(section, null);
                PropertyInfo kind = Member(page, "PaperKind");
                kind.SetValue(page, Enum.Parse(kind.PropertyType, "A3"), null);
                Member(page, "Landscape").SetValue(page, true, null);
                count++;
            }
            if (count == 0) throw new InvalidOperationException("Mẫu khám sức khỏe không có trang để in.");
        }
        public static bool UseDuplex(bool a3Supported, bool duplexSupported, bool microsoftPdf)
        {
            if (!a3Supported) throw new InvalidOperationException("Máy in giấy khám sức khỏe không hỗ trợ khổ A3.");
            if (duplexSupported) return true;
            if (microsoftPdf) return false; // File export has no physical two-sided mode.
            throw new InvalidOperationException("Máy in giấy khám sức khỏe chưa hỗ trợ/bật in hai mặt tự động. Hãy kiểm tra driver hoặc chọn máy khác.");
        }
    }
}
