using System;
using DKS.QuickPay;
int passed = 0;
void Debt(decimal gross, decimal discount, decimal paid, decimal coverage, decimal expected) {
    if (Rules.ExamDebt(gross, discount, paid, coverage) != expected) throw new Exception("Wrong debt"); passed++;
}
Debt(140000, 0, 0, 0, 140000);
Debt(140000, 0, 40000, 0, 100000);
Debt(140000, 0, 140000, 0, 0);
Debt(140000, 0, 160000, 0, 0);
Debt(140000, 10000, 40000, 20, 62000);
Debt(140000, 0, 0, 100, 0);
Debt(0, 0, 0, 0, 0);
foreach (var a in new[] { new decimal[]{-1,0,0,0}, new decimal[]{1,-1,0,0}, new decimal[]{1,0,-1,0}, new decimal[]{1,0,0,-1}, new decimal[]{1,0,0,101} }) {
    try { Rules.ExamDebt(a[0],a[1],a[2],a[3]); throw new Exception("Expected rejection"); }
    catch (ArgumentOutOfRangeException) { passed++; }
}
Console.WriteLine(passed + " debt scenarios passed; runtime SQL/WinForms checks still required.");
TransactionTests.Run();
string settingsFile = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "DKS-printer-tests-" + Guid.NewGuid().ToString("N"), "printers.xml");
if (System.IO.File.Exists(settingsFile)) System.IO.File.Delete(settingsFile);
var choices = new PrinterOptions { HealthPrinter = "Máy in A3 \\PC\\KSK", RecordPrinter = "Máy in A4 bệnh án" };
choices.SaveTo(settingsFile);
var saved = PrinterOptions.ReadFrom(settingsFile);
if (saved.HealthPrinter != choices.HealthPrinter || saved.RecordPrinter != choices.RecordPrinter) throw new Exception("Printer choices not restored independently");
choices.RecordPrinter = "Máy thứ hai mới"; choices.SaveTo(settingsFile);
saved = PrinterOptions.ReadFrom(settingsFile);
if (saved.HealthPrinter != choices.HealthPrinter || saved.RecordPrinter != choices.RecordPrinter) throw new Exception("Printer update lost a choice");
System.IO.File.Delete(settingsFile);
System.IO.Directory.Delete(System.IO.Path.GetDirectoryName(settingsFile));
Console.WriteLine("2 printer persistence scenarios passed; no physical printer tested.");
