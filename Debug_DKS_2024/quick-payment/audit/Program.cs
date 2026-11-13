using dnlib.DotNet;
using dnlib.DotNet.Emit;
using System.Text.Json;
using System.Security.Cryptography;
if (args.Length != 3) throw new ArgumentException("Usage: Audit original.exe revised.exe results.json");
using var original = ModuleDefMD.Load(args[0]);
using var revised = ModuleDefMD.Load(args[1]);
string Op(Instruction i, CilBody body) => i.OpCode.Name + ":" + (i.Operand switch {
 null=>"", Instruction target=>"branch:"+body.Instructions.IndexOf(target), IList<Instruction> targets=>string.Join(",",targets.Select(t=>body.Instructions.IndexOf(t))),
 IMethod m=>m.FullName,IField f=>f.FullName,ITypeDefOrRef t=>t.FullName,Local l=>"local:"+l.Index+":"+l.Type.FullName,Parameter p=>"arg:"+p.Index,_=>i.Operand.ToString()
});
var after = revised.GetTypes().SelectMany(t=>t.Methods).ToDictionary(m=>m.FullName);
bool Equal(MethodDef a,MethodDef b) => a.HasBody == b.HasBody && (!a.HasBody || (a.Body.Instructions.Select(i=>Op(i,a.Body)).SequenceEqual(b.Body.Instructions.Select(i=>Op(i,b.Body))) && a.Body.ExceptionHandlers.Count == b.Body.ExceptionHandlers.Count && a.Body.Variables.Select(v=>v.Type.FullName).SequenceEqual(b.Body.Variables.Select(v=>v.Type.FullName))));
var changed=original.GetTypes().SelectMany(t=>t.Methods).Where(m=>!Equal(m,after[m.FullName])).Select(m=>m.FullName).ToArray();
var reportClasses=original.GetTypes().Where(t=>t.FullName.Contains("BAOCAO",StringComparison.OrdinalIgnoreCase)||t.Name.String.Contains("XtraReport")||t.Name.String.Contains("BaoCao")).ToArray();
var reportMethods=reportClasses.SelectMany(t=>t.Methods).ToArray();
var host=original.Types.Single(t=>t.FullName=="_247Dental.Form1");
string[] names={"barButtonItem1_ItemClick","barButtonItem2_ItemClick","barButtonItem3_ItemClick","bntBaocaotonghopthuchi_ItemClick","bntBaoCaoThuTienKhamBenh_ItemClick","bntTongHopKhamBenh_ItemClick","barButtonItem10_ItemClick","barButtonItem12_ItemClick","barButtonItem8_ItemClick","btnBaocaocongno_ItemClick"};
var entries=names.Select(name=>{
 var m=host.Methods.Single(m=>m.Name==name);
 var created=m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Newobj&&i.Operand is IMethod).Select(i=>((IMethod)i.Operand).DeclaringType.FullName).Distinct().ToArray();
 var forms=created.Select(n=>original.Find(n,false)).Where(t=>t!=null).ToArray();
 return new {handler=name,unchanged=Equal(m,after[m.FullName]),forms=created,formMethods=forms.Sum(t=>t.Methods.Count),formChanged=forms.SelectMany(t=>t.Methods).Count(x=>!Equal(x,after[x.FullName])),dataCalls=forms.SelectMany(t=>t.Methods).Where(x=>x.HasBody).SelectMany(x=>x.Body.Instructions).Where(i=>i.Operand is IMethod cm&&cm.DeclaringType.FullName.StartsWith("_247Dental.Data.")).Select(i=>((IMethod)i.Operand).FullName).Distinct().ToArray()};
}).ToArray();
var resources=original.Resources.OfType<EmbeddedResource>().ToArray();
bool resourcesEqual=resources.All(r=>revised.Resources.OfType<EmbeddedResource>().Single(a=>a.Name==r.Name).CreateReader().ToArray().SequenceEqual(r.CreateReader().ToArray()));
var result=new {methods=after.Count,changed,reportClasses=reportClasses.Length,reportMethods=reportMethods.Length,reportMethodChanges=reportMethods.Where(m=>!Equal(m,after[m.FullName])).Select(m=>m.FullName).ToArray(),embeddedResources=resources.Length,resourcesEqual,entries};
File.WriteAllText(args[2],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine(JsonSerializer.Serialize(new {result.methods,result.changed,result.reportClasses,result.reportMethods,result.reportMethodChanges,result.embeddedResources,result.resourcesEqual,entries=entries.Select(e=>new{e.handler,e.unchanged,e.forms,e.formMethods,e.formChanged})},new JsonSerializerOptions{WriteIndented=true}));
foreach(var path in new[]{args[1],Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1]))!,"DKS.QuickPay.dll")}){
 var b=File.ReadAllBytes(path);var header=System.Text.Encoding.UTF8.GetBytes("blob "+b.Length+"\0");Console.WriteLine(Path.GetFileName(path)+" git-sha1="+Convert.ToHexString(SHA1.HashData(header.Concat(b).ToArray())).ToLowerInvariant());
}
