using TwicArchiveManager.Core.Models;

namespace TwicArchiveManager.Core.Planning;

public static class SyncPlanner
{
    public static IReadOnlyList<SyncPlanItem> Create(
        IEnumerable<TwicIssue> catalog,
        IEnumerable<ManifestArtifact> manifestArtifacts,
        ArchiveProfile profile,
        SyncSelection selection)
    {
        ArgumentNullException.ThrowIfNull(catalog);
        ArgumentNullException.ThrowIfNull(manifestArtifacts);
        ArgumentNullException.ThrowIfNull(profile);
        ArgumentNullException.ThrowIfNull(selection);

        var orderedIssues = catalog
            .Where(static issue => issue.Number > 0)
            .GroupBy(static issue => issue.Number)
            .Select(static group => group.First())
            .OrderBy(static issue => issue.Number)
            .ToArray();

        var selectedIssues = SelectIssues(orderedIssues, selection);
        var artifactByKey = manifestArtifacts.ToDictionary(
            static artifact => (artifact.IssueNumber, artifact.Format));

        var plan = new List<SyncPlanItem>();
        foreach (var issue in selectedIssues)
        {
            foreach (var format in profile.SelectedFormats)
            {
                var source = issue.GetSource(format);
                var hasExisting = artifactByKey.TryGetValue((issue.Number, format), out var existing);
                var needsRepair = !hasExisting || IsDamagedOrIncomplete(existing!);

                plan.Add(new SyncPlanItem(
                    issue,
                    format,
                    source,
                    hasExisting ? existing!.Status : ArtifactStatus.Unknown,
                    source is not null,
                    needsRepair));
            }
        }

        return plan;
    }

    private static IReadOnlyList<TwicIssue> SelectIssues(
        IReadOnlyList<TwicIssue> orderedIssues,
        SyncSelection selection) => selection.Kind switch
    {
        SyncSelectionKind.InclusiveRange => SelectInclusiveRange(orderedIssues, selection),
        SyncSelectionKind.FromIssueThroughNewest => SelectFromIssue(orderedIssues, selection),
        SyncSelectionKind.LatestCount => SelectLatest(orderedIssues, selection),
        SyncSelectionKind.MissingOrDamagedInScope => SelectInclusiveRange(orderedIssues, selection),
        _ => throw new ArgumentOutOfRangeException(nameof(selection)),
    };

    private static IReadOnlyList<TwicIssue> SelectInclusiveRange(
        IReadOnlyList<TwicIssue> orderedIssues,
        SyncSelection selection)
    {
        if (selection.FromIssue is not > 0 || selection.ToIssue is not > 0 || selection.FromIssue > selection.ToIssue)
        {
            throw new ArgumentException("An inclusive range requires a positive From issue not greater than To issue.", nameof(selection));
        }

        return orderedIssues
            .Where(issue => issue.Number >= selection.FromIssue && issue.Number <= selection.ToIssue)
            .ToArray();
    }

    private static IReadOnlyList<TwicIssue> SelectFromIssue(
        IReadOnlyList<TwicIssue> orderedIssues,
        SyncSelection selection)
    {
        if (selection.FromIssue is not > 0)
        {
            throw new ArgumentException("This selection requires a positive starting issue.", nameof(selection));
        }

        return orderedIssues.Where(issue => issue.Number >= selection.FromIssue).ToArray();
    }

    private static IReadOnlyList<TwicIssue> SelectLatest(
        IReadOnlyList<TwicIssue> orderedIssues,
        SyncSelection selection)
    {
        if (selection.LatestCount is not > 0)
        {
            throw new ArgumentException("Latest count must be positive.", nameof(selection));
        }

        return orderedIssues.TakeLast(selection.LatestCount.Value).ToArray();
    }

    private static bool IsDamagedOrIncomplete(ManifestArtifact artifact) =>
        artifact.Status is not (ArtifactStatus.Verified or ArtifactStatus.Extracted) ||
        string.IsNullOrWhiteSpace(artifact.ZipRelativePath) ||
        artifact.ZipSize is not > 0 ||
        string.IsNullOrWhiteSpace(artifact.ZipSha256);
}
