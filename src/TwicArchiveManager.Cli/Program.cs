namespace TwicArchiveManager.Cli;

internal static class Program
{
    private const string BuildHandoffMessage =
        "TWIC Archive Manager CLI scaffold. Implement sync, combine, verify, and status as specified in CODEX_BUILD_HANDOFF.md.";

    public static int Main(string[] args)
    {
        if (args.Length == 0 || args[0] is "--help" or "-h")
        {
            Console.WriteLine(BuildHandoffMessage);
            Console.WriteLine("Planned commands: sync, combine, verify, status.");
            return 0;
        }

        Console.Error.WriteLine($"{BuildHandoffMessage} Received command: {args[0]}");
        return 2;
    }
}
