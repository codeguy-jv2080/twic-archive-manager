namespace TwicArchiveManager.Core.Models;

public sealed record ManifestArtifact(
    int IssueNumber,
    ArchiveFormat Format,
    ArtifactStatus Status,
    string? ZipRelativePath,
    long? ZipSize,
    string? ZipSha256,
    DateTimeOffset? DownloadedAt,
    bool Extracted,
    IReadOnlyList<string> ExtractedRelativePaths,
    int AttemptCount,
    string? LastError,
    bool IncludedInCombinedPgn);
