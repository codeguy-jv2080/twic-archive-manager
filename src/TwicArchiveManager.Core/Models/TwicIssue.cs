namespace TwicArchiveManager.Core.Models;

public sealed record TwicIssue(
    int Number,
    DateOnly? PublicationDate,
    Uri? PgnZipUri,
    Uri? CbvZipUri,
    int? GameCount)
{
    public Uri? GetSource(ArchiveFormat format) => format switch
    {
        ArchiveFormat.Pgn => PgnZipUri,
        ArchiveFormat.Cbv => CbvZipUri,
        _ => null,
    };
}
