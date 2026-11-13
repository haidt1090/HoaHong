using System;
using System.Collections;
using System.Data;
using System.Threading;
using DKS.QuickPay;

static class TransactionTests
{
    static void Assert(bool condition, string message) { if (!condition) throw new Exception(message); }
    public static int Run()
    {
        int passed = 0;
        var c = new FakeConnection();
        using (var session = Database.Begin(c))
        {
            Database.Write("Receipt"); Database.Write("Stock"); Database.Write("Audit");
            var table = Database.Read("Balance"); Assert((int)table.Rows[0][0] == 0, "Read failed");
            session.Complete();
        }
        Assert(c.Commits == 1 && c.Rollbacks == 0 && c.Published.Count == 3, "Not committed together");
        Assert(c.BeginCount == 1 && c.OpenCount == 0 && c.CommandsWithWrongTransaction == 0, "Not a single local transaction");
        Assert(!Database.IsActive(), "Leaked payment context"); passed += 3;
        c = new FakeConnection();
        using (var session = Database.Begin(c)) { Database.Write("Receipt"); Database.Write("Stock"); }
        Assert(c.Commits == 0 && c.Rollbacks == 1 && c.Published.Count == 0, "Incomplete transaction published writes"); passed++;
        c = new FakeConnection();
        using (var session = Database.Begin(c))
        {
            Database.Write("Receipt");
            try { Database.Write("Fail"); } catch (InvalidOperationException) { }
            try { session.Complete(); throw new Exception("Swallowed SQL error committed"); } catch (InvalidOperationException) { }
        }
        Assert(c.Commits == 0 && c.Rollbacks == 1 && c.Published.Count == 0, "Failure didn't roll back"); passed++;
        c = new FakeConnection();
        using (var session = Database.Begin(c))
        {
            bool otherThreadActive = true;
            var thread = new Thread(() => otherThreadActive = Database.IsActive()); thread.Start(); thread.Join();
            Assert(!otherThreadActive && Database.IsActive(), "Context leaked across threads");
            try { Database.Begin(c); throw new Exception("Nested context allowed"); } catch (InvalidOperationException) { }
        }
        Assert(!Database.IsActive(), "Context didn't reset"); passed++;
        c = new FakeConnection { DenyLock = true };
        try { Database.Begin(c); throw new Exception("Concurrent lock allowed"); } catch (InvalidOperationException) { }
        Assert(c.Rollbacks == 1 && !Database.IsActive(), "Lock failure leaked context"); passed++;
        Console.WriteLine(passed + " local-transaction scenarios passed using an ADO.NET fake (not SQL Server)."); return passed;
    }
    sealed class FakeConnection : IDbConnection
    {
        public int BeginCount, OpenCount, Commits, Rollbacks, CommandsWithWrongTransaction;
        public bool DenyLock;
        public ArrayList Pending = new ArrayList(), Published = new ArrayList();
        public FakeTransaction Current;
        public string ConnectionString { get; set; }
        public int ConnectionTimeout => 0; public string Database => "Test"; public ConnectionState State => ConnectionState.Open;
        public IDbTransaction BeginTransaction() => BeginTransaction(IsolationLevel.Serializable);
        public IDbTransaction BeginTransaction(IsolationLevel level) { if(level!=IsolationLevel.Serializable) throw new Exception("Wrong isolation"); BeginCount++; return Current = new FakeTransaction(this); }
        public void Open() { OpenCount++; } public void Close() { } public void ChangeDatabase(string name) { } public void Dispose() { }
        public IDbCommand CreateCommand() => new FakeCommand(this);
    }
    sealed class FakeTransaction : IDbTransaction
    {
        readonly FakeConnection connection; bool done;
        public FakeTransaction(FakeConnection c) { connection = c; }
        public IDbConnection Connection => done ? null : connection; public IsolationLevel IsolationLevel => IsolationLevel.Serializable;
        public void Commit() { connection.Commits++; connection.Published.AddRange(connection.Pending); done = true; }
        public void Rollback() { connection.Rollbacks++; connection.Pending.Clear(); done = true; }
        public void Dispose() { }
    }
    sealed class FakeCommand : IDbCommand
    {
        readonly FakeConnection c;
        public FakeCommand(FakeConnection connection) { c = connection; }
        public string CommandText { get; set; } public int CommandTimeout { get; set; } public CommandType CommandType { get; set; }
        public IDbConnection Connection { get; set; } public IDbTransaction Transaction { get; set; } public UpdateRowSource UpdatedRowSource { get; set; }
        public IDataParameterCollection Parameters => throw new NotSupportedException(); public IDbDataParameter CreateParameter() => throw new NotSupportedException();
        void Validate() { if (!ReferenceEquals(Transaction,c.Current)) { c.CommandsWithWrongTransaction++; throw new Exception("Wrong transaction"); } if(CommandText=="Fail")throw new InvalidOperationException("SQL failure"); }
        public int ExecuteNonQuery() { Validate(); c.Pending.Add(CommandText); return 1; }
        public object ExecuteScalar() { Validate(); return c.DenyLock ? -1 : 0; }
        public IDataReader ExecuteReader() { Validate(); var t=new DataTable();t.Columns.Add("debt",typeof(int));t.Rows.Add(0); return t.CreateDataReader(); }
        public IDataReader ExecuteReader(CommandBehavior b) => ExecuteReader(); public void Cancel() { } public void Prepare() { } public void Dispose() { }
    }
}
