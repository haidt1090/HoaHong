using System;
using System.Linq;
using DKS.QuickPay;
static class CopyPlanTests
{
    public static void Run()
    {
        foreach (var test in new[] {
            new[]{1,999,1}, new[]{3,999,1}, new[]{3,1,3}, new[]{3,2,2}, new[]{3,0,3}, new[]{99,50,2}
        })
        {
            var jobs = CopyPlan.Jobs(test[0],test[1]).ToArray();
            if(jobs.Sum()!=test[0] || jobs.Length!=test[2] || jobs.Any(n=>n<1 || n>Math.Max(1,test[1]))) throw new Exception("Wrong number of printed sets");
        }
        foreach(int n in new[]{0,100}) { try { CopyPlan.Jobs(n,999).ToArray(); throw new Exception("Invalid copy count accepted"); } catch(ArgumentOutOfRangeException){} }
        Console.WriteLine("8 copy-count scenarios passed; collated physical printing still needs a driver test.");
    }
}
