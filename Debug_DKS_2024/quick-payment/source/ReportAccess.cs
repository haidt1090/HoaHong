using System;
using System.Reflection;
namespace DKS.QuickPay
{
    public static class ReportAccess
    {
        public static object FromPreview(object preview)
        {
            if (preview == null) throw new ArgumentNullException("preview");
            // The original frm_SHOW_PHIEU_KHAMBENH.MyReport is setter-only.
            // Its setter stores the report in the private reportMain field.
            for (Type type = preview.GetType(); type != null; type = type.BaseType)
            {
                var field = type.GetField("reportMain", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field == null) continue;
                object report = field.GetValue(preview);
                if (report == null) throw new InvalidOperationException("Bệnh án chưa có báo cáo để in.");
                return report;
            }
            throw new MissingFieldException(preview.GetType().FullName, "reportMain");
        }
    }
}
