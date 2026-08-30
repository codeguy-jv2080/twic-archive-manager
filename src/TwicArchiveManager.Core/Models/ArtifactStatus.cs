namespace TwicArchiveManager.Core.Models;

public enum ArtifactStatus
{
    Unknown,
    Planned,
    Downloading,
    Verified,
    Extracted,
    Unavailable,
    Failed,
    Canceled,
}
