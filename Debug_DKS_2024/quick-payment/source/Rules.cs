using System;
namespace DKS.QuickPay
{
    public static class Rules
    {
        public static decimal ExamDebt(decimal gross, decimal discount, decimal paid, decimal coverage)
        {
            if (gross < 0 || discount < 0 || paid < 0 || coverage < 0 || coverage > 100)
                throw new ArgumentOutOfRangeException("Invalid payment amounts");
            return Math.Max(0m, gross - discount - paid - gross * coverage / 100m);
        }
    }
}
