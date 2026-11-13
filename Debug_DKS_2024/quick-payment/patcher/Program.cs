using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System.Security.Cryptography;

if (args.Length != 3) throw new ArgumentException("Usage: patcher original.exe DKS.QuickPay.dll patched.exe");
const string originalSha256 = "5abb1bc6e4be8659bce4544a42b39e1f989a98d72219c589ef89b3e562bc7a59";
if (Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[0]))).ToLowerInvariant() != originalSha256)
    throw new InvalidOperationException("Unsupported original executable hash; no file written.");
using var module = ModuleDefMD.Load(args[0]);
using var helper = ModuleDefMD.Load(args[1]);
var payment = module.Types.Single(t => t.FullName == "_247Dental.Design.Work.uc_Nghiepvu")
    .Methods.Single(m => m.Name == "btnThanhtoan_Click");
var run = helper.Types.Single(t => t.FullName == "DKS.QuickPay.Payment").Methods.Single(m => m.Name == "Run");
var calls = payment.Body.Instructions.Where(i => i.OpCode == OpCodes.Callvirt && i.Operand is IMethod m && m.FullName.Contains("System.Windows.Forms.Form::ShowDialog()")).ToArray();
if (calls.Length != 1) throw new InvalidOperationException("Expected exactly one payment dialog call.");
calls[0].OpCode = OpCodes.Call;
calls[0].Operand = new Importer(module).Import(run);
module.Write(args[2]);
using var check = ModuleDefMD.Load(args[2]);
var method = check.Types.Single(t => t.FullName == "_247Dental.Design.Work.uc_Nghiepvu").Methods.Single(m => m.Name == "btnThanhtoan_Click");
if (method.Body.Instructions.Count(i => i.Operand is IMethod m && m.FullName.Contains("DKS.QuickPay.Payment::Run")) != 1)
    throw new InvalidOperationException("Verification failed.");
Console.WriteLine("Patched only the payment dialog call; wrote " + args[2]);
using var baseline = ModuleDefMD.Load(args[0]);
string Op(Instruction instruction, CilBody body) => instruction.OpCode.Name + ":" + (instruction.Operand switch {
    null => "", Instruction target => "branch:" + body.Instructions.IndexOf(target),
    IList<Instruction> targets => string.Join(",", targets.Select(t => body.Instructions.IndexOf(t))),
    IMethod m => m.FullName, IField f => f.FullName, ITypeDefOrRef t => t.FullName,
    Local l => "local:" + l.Index + ":" + l.Type.FullName, Parameter p => "arg:" + p.Index,
    _ => instruction.Operand.ToString()
});
var revised = check.GetTypes().SelectMany(t => t.Methods).ToDictionary(m => m.FullName);
int methodCount = 0, instructionChanges = 0;
foreach (var before in baseline.GetTypes().SelectMany(t => t.Methods)) {
    var after = revised[before.FullName]; methodCount++;
    if (before.HasBody != after.HasBody) throw new Exception("Method body presence changed.");
    if (!before.HasBody) continue;
    if (before.Body.Instructions.Count != after.Body.Instructions.Count) throw new Exception("Instruction count changed: " + before.FullName);
    for (int i = 0; i < before.Body.Instructions.Count; i++) {
        if (Op(before.Body.Instructions[i], before.Body) == Op(after.Body.Instructions[i], after.Body)) continue;
        if (before.FullName != payment.FullName || before.Body.Instructions[i].Operand is not IMethod old || old.Name != "ShowDialog" || after.Body.Instructions[i].Operand is not IMethod replacement || replacement.Name != "Run")
            throw new Exception("Unexpected instruction change: " + before.FullName + " #" + i);
        instructionChanges++;
    }
    if (before.Body.ExceptionHandlers.Count != after.Body.ExceptionHandlers.Count) throw new Exception("Exception handler count changed.");
    if (before.Body.Variables.Select(v => v.Type.FullName).SequenceEqual(after.Body.Variables.Select(v => v.Type.FullName)) == false) throw new Exception("Local variable types changed.");
}
if (methodCount != revised.Count || instructionChanges != 1) throw new Exception("Unexpected method/instruction changes.");
if (!baseline.Resources.Select(r => r.Name).SequenceEqual(check.Resources.Select(r => r.Name))) throw new Exception("Resources changed.");
Console.WriteLine($"Verified {methodCount} method bodies/signatures: exactly {instructionChanges} call replaced; resource names preserved.");
