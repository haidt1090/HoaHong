using System;
using System.Collections.Generic;
namespace DKS.QuickPay
{
    public static class CopyPlan
    {
        public static IEnumerable<int> Jobs(int copies, int driverMaximum)
        {
            if (copies < 1 || copies > 99) throw new ArgumentOutOfRangeException("copies", "Số lượng phải từ 1 đến 99.");
            int capacity = Math.Max(1, driverMaximum);
            while (copies > 0) { int batch = Math.Min(copies, capacity); yield return batch; copies -= batch; }
        }
    }
}
