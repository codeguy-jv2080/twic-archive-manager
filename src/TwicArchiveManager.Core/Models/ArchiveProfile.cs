namespace TwicArchiveManager.Core.Models;

public sealed record ArchiveProfile(
    string Name,
    string ArchiveRoot,
    bool DownloadPgn,
    bool DownloadCbv,
    bool ExtractArchives = true,
    bool KeepZipFiles = true,
    bool CombinePgnAfterSync = false)
{
    public IReadOnlyList<ArchiveFormat> SelectedFormats =>
        new[]
        {
            DownloadPgn ? ArchiveFormat.Pgn : (ArchiveFormat?)null,
            DownloadCbv ? ArchiveFormat.Cbv : (ArchiveFormat?)null,
        }
        .Where(static format => format.HasValue)
        .Select(static format => format!.Value)
        .ToArray();
}
