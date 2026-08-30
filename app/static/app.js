const statusMessage = document.querySelector("#connection-status");
const formMessage = document.querySelector("#form-message");
const profileList = document.querySelector("#profiles");
const profileForm = document.querySelector("#profile-form");

async function loadProfiles() {
  const response = await fetch("/api/profiles");
  const profiles = await response.json();
  profileList.replaceChildren(
    ...profiles.map((profile) => {
      const item = document.createElement("li");
      const formats = [profile.download_pgn && "PGN", profile.download_cbv && "CBV"].filter(Boolean).join(" + ");
      item.textContent = `${profile.name}: ${profile.archive_root} (${formats}; ZIPs ${profile.keep_zip_files ? "kept" : "deleted after extraction"})`;
      return item;
    }),
  );
}

async function initialize() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    statusMessage.textContent = health.status === "ok" ? "Local application ready." : "Local application is unavailable.";
    await loadProfiles();
  } catch {
    statusMessage.textContent = "Could not connect to the local application.";
  }
}

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(profileForm);
  const body = {
    name: data.get("name"),
    archive_root: data.get("archive_root"),
    download_pgn: data.has("download_pgn"),
    download_cbv: data.has("download_cbv"),
    extract_archives: data.has("extract_archives"),
    keep_zip_files: data.has("keep_zip_files"),
    combine_after_sync: data.has("combine_after_sync"),
  };

  const response = await fetch("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    formMessage.textContent = result.detail || "Could not save the profile.";
    return;
  }
  formMessage.textContent = "Profile saved.";
  profileForm.reset();
  profileForm.elements.download_pgn.checked = true;
  profileForm.elements.extract_archives.checked = true;
  profileForm.elements.keep_zip_files.checked = true;
  await loadProfiles();
});

initialize();
