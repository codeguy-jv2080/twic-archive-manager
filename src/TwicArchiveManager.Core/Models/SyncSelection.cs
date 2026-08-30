namespace TwicArchiveManager.Core.Models;

public enum SyncSelectionKind
{
    InclusiveRange,
    FromIssueThroughNewest,
    LatestCount,
    MissingOrDamagedInScope,
}

public sealed record SyncSelection(
    SyncSelectionKind Kind,
    int? FromIssue = null,
    int? ToIssue = null,
    int? LatestCount = null)
{
    public static SyncSelection LatestOne { get; } =
        new(SyncSelectionKind.LatestCount, LatestCount: 1);
}
