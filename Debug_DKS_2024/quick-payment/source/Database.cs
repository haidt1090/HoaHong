using System;
using System.Data;

namespace DKS.QuickPay
{
    // Only the payment thread uses this context. Other screens use the original data layer.
    public static class Database
    {
        [ThreadStatic] static Session current;
        public static bool IsActive() { return current != null; }
        public static Session Begin(IDbConnection connection)
        {
            if (current != null) throw new InvalidOperationException("Đang có giao dịch thanh toán.");
            var session = new Session(connection);
            current = session;
            try
            {
                using (var command = session.Command("SET XACT_ABORT ON; DECLARE @r int; EXEC @r=sys.sp_getapplock @Resource=N'DKS.QuickPay.All', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=0; SELECT @r;", CommandType.Text, null, null, 0))
                    if (Convert.ToInt32(command.ExecuteScalar()) < 0) throw new InvalidOperationException("Đang có thanh toán khác. Vui lòng thử lại.");
                return session;
            }
            catch { session.Dispose(); throw; }
        }
        public static DataTable Read(string sql) { return Read(sql, null, null, 0); }
        public static DataTable Read(string sql, string[] names, object[] values, int count)
        { return ReadCore(sql, CommandType.StoredProcedure, names, values, count); }
        public static DataTable ReadText(string sql) { return ReadCore(sql, CommandType.Text, null, null, 0); }
        static DataTable ReadCore(string sql, CommandType kind, string[] names, object[] values, int count)
        {
            try
            {
                using (var command = current.Command(sql, kind, names, values, count))
                using (var reader = command.ExecuteReader())
                { var table = new DataTable(); table.Load(reader); return table; }
            }
            catch (Exception ex) { if (current != null) current.Failure = ex; throw; }
        }
        public static int Write(string sql) { return Write(sql, null, null, 0); }
        public static int Write(string sql, string[] names, object[] values, int count)
        {
            try
            {
                using (var command = current.Command(sql, CommandType.StoredProcedure, names, values, count))
                    return command.ExecuteNonQuery();
            }
            catch (Exception ex) { if (current != null) current.Failure = ex; throw; }
        }
        public sealed class Session : IDisposable
        {
            readonly IDbConnection connection;
            readonly IDbTransaction transaction;
            bool completed;
            internal Exception Failure;
            internal Session(IDbConnection c) { connection = c; transaction = c.BeginTransaction(IsolationLevel.Serializable); }
            internal IDbCommand Command(string sql, CommandType kind, string[] names, object[] values, int count)
            {
                if (Failure != null) throw new InvalidOperationException("Giao dịch đã gặp lỗi SQL; không thể tiếp tục.", Failure);
                if (completed || transaction.Connection == null) throw new InvalidOperationException("Giao dịch không còn hiệu lực.");
                var command = connection.CreateCommand();
                command.Transaction = transaction; command.CommandText = sql; command.CommandType = kind; command.CommandTimeout = 120;
                try
                {
                    for (int i = 0; i < count; i++)
                    {
                        var parameter = command.CreateParameter(); parameter.ParameterName = names[i]; parameter.Value = values[i] ?? DBNull.Value;
                        command.Parameters.Add(parameter);
                    }
                    return command;
                }
                catch { command.Dispose(); throw; }
            }
            public void Complete()
            {
                if (Failure != null) throw new InvalidOperationException("Không lưu thanh toán vì có lỗi SQL: " + Failure.Message, Failure);
                transaction.Commit(); completed = true;
            }
            public void Dispose()
            {
                try { if (!completed && transaction.Connection != null) transaction.Rollback(); }
                finally
                {
                    try { transaction.Dispose(); }
                    finally { if (ReferenceEquals(current, this)) current = null; }
                }
            }
        }
    }
}
