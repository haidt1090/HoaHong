using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System.Security.Cryptography;

if (args.Length != 3) throw new ArgumentException("Usage: patcher original.exe DKS.QuickPay.dll patched.exe");
const string originalSha256 = "5abb1bc6e4be8659bce4544a42b39e1f989a98d72219c589ef89b3e562bc7a59";
if (Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant() != originalSha256)
    throw new InvalidOperationException("Unsupported original executable hash; no file written.");
using var module = ModuleDefMD.Load(args[0]);
using var helper = ModuleDefMD.Load(args[1]);
var importer = new Importer(module);
var touched = new HashSet<string>();
IMethod Import(string type, string name, int parameters) => importer.Import(helper.Types.Single(t => t.FullName == type).Methods.Single(m => m.Name == name && m.MethodSig.Params.Count == parameters));
MethodDef Original(string type, string name) => module.Types.Single(t => t.FullName == type).Methods.Single(m => m.Name == name);
Instruction DialogCall(MethodDef method) => method.Body.Instructions.Single(i => i.OpCode == OpCodes.Callvirt && i.Operand is IMethod m && m.FullName.Contains("System.Windows.Forms.Form::ShowDialog()"));
void ReplaceDialog(MethodDef method, IMethod target) {
    var call = DialogCall(method); call.OpCode = OpCodes.Call; call.Operand = target; touched.Add(method.FullName);
}
const string host = "_247Dental.Design.Work.uc_Nghiepvu";
ReplaceDialog(Original(host, "btnThanhtoan_Click"), Import("DKS.QuickPay.Payment", "Run", 1));
ReplaceDialog(Original(host, "btnInhoso_Click"), Import("DKS.QuickPay.Printing", "ReportPreview", 1));
var menu = Original(host, "simpleButton3_Click");
var show = DialogCall(menu);
menu.Body.Instructions.Insert(menu.Body.Instructions.IndexOf(show), Instruction.Create(OpCodes.Ldarg_0));
show.OpCode = OpCodes.Call; show.Operand = Import("DKS.QuickPay.Printing", "ShowMenu", 2); touched.Add(menu.FullName);
// Only route the existing data-access methods when a quick-payment local transaction is active.
var data = module.Types.Single(t => t.FullName == "_247Dental.Data.KetNoiCSDL_Data");
var routes = data.Methods.Where(m => m.Name == "taobang" || m.Name == "LayDuLieu" || m.Name == "update").ToArray();
if (routes.Length != 5) throw new Exception("Unexpected SQL data layer.");
foreach (var method in routes) {
    string target = method.Name == "taobang" ? "ReadText" : method.Name == "update" ? "Write" : "Read";
    int count = method.MethodSig.Params.Count;
    var originalStart = method.Body.Instructions[0];
    var prologue = new List<Instruction> { Instruction.Create(OpCodes.Call, Import("DKS.QuickPay.Database", "IsActive", 0)), Instruction.Create(OpCodes.Brfalse, originalStart) };
    foreach (var parameter in method.Parameters.Where(p => !p.IsHiddenThisParameter)) prologue.Add(Instruction.Create(OpCodes.Ldarg, parameter));
    prologue.Add(Instruction.Create(OpCodes.Call, Import("DKS.QuickPay.Database", target, count))); prologue.Add(Instruction.Create(OpCodes.Ret));
    for (int i = 0; i < prologue.Count; i++) method.Body.Instructions.Insert(i, prologue[i]);
    touched.Add(method.FullName);
}
module.Write(args[2]);
using var check = ModuleDefMD.Load(args[2]);
using var baseline = ModuleDefMD.Load(args[0]);
string Op(Instruction instruction, CilBody body) => instruction.OpCode.Name + ":" + (instruction.Operand switch {
    null => "", Instruction target => "branch:" + body.Instructions.IndexOf(target),
    IList<Instruction> targets => string.Join(",", targets.Select(t => body.Instructions.IndexOf(t))),
    IMethod m => m.FullName, IField f => f.FullName, ITypeDefOrRef t => t.FullName,
    Local l => "local:" + l.Index + ":" + l.Type.FullName, Parameter p => "arg:" + p.Index,
    _ => instruction.Operand.ToString()
});
var revised = check.GetTypes().SelectMany(t => t.Methods).ToDictionary(m => m.FullName);
int methodCount = 0;
foreach (var before in baseline.GetTypes().SelectMany(t => t.Methods)) {
    var after = revised[before.FullName]; methodCount++;
    if (before.HasBody != after.HasBody) throw new Exception("Method body presence changed.");
    if (!before.HasBody) continue;
    if (!touched.Contains(before.FullName) && !before.Body.Instructions.Select(i => Op(i,before.Body)).SequenceEqual(after.Body.Instructions.Select(i => Op(i,after.Body))))
        throw new Exception("Unexpected method change: " + before.FullName);
    if (before.Body.ExceptionHandlers.Count != after.Body.ExceptionHandlers.Count) throw new Exception("Exception handlers changed.");
    if (!before.Body.Variables.Select(v => v.Type.FullName).SequenceEqual(after.Body.Variables.Select(v => v.Type.FullName))) throw new Exception("Local types changed.");
}
if (methodCount != revised.Count || touched.Count != 8) throw new Exception("Unexpected method changes.");
if (!baseline.Resources.Select(r => r.Name).SequenceEqual(check.Resources.Select(r => r.Name))) throw new Exception("Resources changed.");
foreach (var resource in baseline.Resources.OfType<EmbeddedResource>()) {
    var after = (EmbeddedResource)check.Resources.Single(r => r.Name == resource.Name);
    if (!resource.CreateReader().ToArray().SequenceEqual(after.CreateReader().ToArray())) throw new Exception("Resource bytes changed.");
}
foreach (var method in check.Types.Single(t => t.FullName == "_247Dental.Data.KetNoiCSDL_Data").Methods.Where(m => m.Name == "taobang" || m.Name == "LayDuLieu" || m.Name == "update")) {
    if (method.Body.Instructions[0].Operand is not IMethod m || m.Name != "IsActive") throw new Exception("Missing SQL route guard.");
}
Console.WriteLine($"Verified {methodCount} methods: exactly {touched.Count} patched entry points, all other IL and embedded resource bytes preserved.");
