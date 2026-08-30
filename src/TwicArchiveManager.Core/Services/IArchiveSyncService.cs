using TwicArchiveManager.Core.Models;

namespace TwicArchiveManager.Core.Services;

public interface IArchiveSyncService
{
    Task<SyncResult> SyncAsync(ArchiveProfile profile, SyncSelection selection, bool dryRun, CancellationToken cancellationToken);

    Task<SyncResult> CombineAsync(ArchiveProfile profile, CancellationToken cancellationToken);

    Task<VerificationResult> VerifyAsync(ArchiveProfile profile, CancellationToken cancellationToken);
}

public sealed record SyncResult(
    int Planned,
    int Succeeded,
    int Failed,
    int Unavailable,
    bool WasCanceled,
    string? Summary = null);

public sealed record VerificationResult(
    int Verified,
    int Damaged,
    int Missing,
    string? Summary = null);
