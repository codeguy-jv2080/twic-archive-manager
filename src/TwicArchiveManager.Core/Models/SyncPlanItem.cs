namespace TwicArchiveManager.Core.Models;

public sealed record SyncPlanItem(
    TwicIssue Issue,
    ArchiveFormat Format,
    Uri? SourceUri,
    ArtifactStatus CurrentStatus,
    bool IsAvailable,
    bool NeedsRepair);
