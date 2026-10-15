import React, { useCallback, useEffect, useState } from "react";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import AuthPage from "./AuthPage.jsx";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const categories = [
  { icon: "⌁", title: "Roads & sidewalks", detail: "Potholes, crossings, pavements", color: "peach" },
  { icon: "☼", title: "Parks & public spaces", detail: "Parks, benches, play areas", color: "lime" },
  { icon: "♧", title: "Waste & cleanliness", detail: "Litter, bins, street cleaning", color: "blue" },
  { icon: "⌁", title: "Water & drainage", detail: "Leaks, flooding, blocked drains", color: "lavender" },
];
const issueTypes = [
  ["roads", "Roads & sidewalks"],
  ["parks", "Parks & public spaces"],
  ["waste", "Waste & cleanliness"],
  ["water", "Water & drainage"],
  ["street_lighting", "Street lighting"],
  ["public_safety", "Public safety"],
  ["other", "Other"],
];
const departments = [
  "Roads & Transport",
  "Parks & Recreation",
  "Waste Management",
  "Water & Drainage",
  "Street Lighting",
  "Public Safety",
  "Other",
];
const mapMarkerIcon = L.divIcon({
  className: "civic-map-marker",
  html: '<span aria-hidden="true"></span>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function BrandMark() {
  return (
    <a className="brand" href="/" aria-label="CivicSense home">
      <span className="brand-icon" aria-hidden="true">
        <svg viewBox="0 0 36 36" fill="none">
          <path d="M18 4.5 30 11v14L18 31.5 6 25V11L18 4.5Z" fill="currentColor" />
          <path d="m12 18 4 4 8-9" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span>Civic<span className="brand-light">Sense</span></span>
    </a>
  );
}

function Header({ currentUser, onSignOut }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <BrandMark />
        <nav className="main-nav" aria-label="Main navigation">
          <a href="/#how-it-works">How it works</a>
          <a href="/#community">Community</a>
        </nav>
        <div className="header-actions">
          <a className="header-reports-link" href="/my-reports">My reports</a>
          {currentUser.is_admin && <a className="header-admin-link" href="/admin">Review queue</a>}
          <NotificationBell />
          <span className="header-greeting">Hi, {currentUser.name.split(" ")[0]}</span>
          <button className="header-signout" type="button" onClick={onSignOut}>Sign out</button>
          <a className="header-cta" href="/#report">Report an issue <span aria-hidden="true">↗</span></a>
        </div>
      </div>
    </header>
  );
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const response = await fetch(`${API_URL}/notifications`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
    });
    if (!response.ok) {
      setError("Notifications are unavailable.");
      return;
    }
    const result = await response.json();
    setItems(result.notifications);
    setUnread(result.unread);
    setError("");
  }, []);

  useEffect(() => { load().catch(() => setError("Could not load notifications.")); }, [load]);

  async function markRead(id) {
    if (!id) return;
    try {
      const response = await fetch(`${API_URL}/notifications/${id}/read`, {
        method: "PATCH",
      headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      });
      if (!response.ok) throw new Error("Could not mark this notification as read.");
      load().catch(() => setError("Could not load notifications."));
    } catch (markError) {
      setError(markError instanceof TypeError ? "Could not update this notification." : markError.message);
    }
  }

  async function markAllRead() {
    try {
      const response = await fetch(`${API_URL}/notifications/read-all`, {
        method: "POST",
      headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      });
      if (!response.ok) throw new Error("Could not mark notifications as read.");
      load().catch(() => setError("Could not load notifications."));
    } catch (markError) {
      setError(markError instanceof TypeError ? "Could not update notifications." : markError.message);
    }
  }

  return (
    <div className="notification-center">
      <button
        className="notification-trigger"
        type="button"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
        onClick={() => {
          const nextOpen = !open;
          setOpen(nextOpen);
          if (nextOpen) load().catch(() => setError("Could not load notifications."));
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {unread > 0 && <span className="notification-count">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <div className="notification-popover">
          <div className="notification-popover-heading">
            <strong>Notifications</strong>
            {unread > 0 && <button type="button" onClick={markAllRead}>Mark all read</button>}
          </div>
          {error ? (
            <p className="notification-empty error-message" role="alert">{error}</p>
          ) : items.length === 0 ? (
            <p className="notification-empty">You’re all caught up.</p>
          ) : (
            <div className="notification-list">
              {items.map((item) => (
                <a
                  key={item.id}
                  className={`notification-item${item.read_at ? "" : " is-unread"}`}
                  href={item.complaint_id ? `/my-reports?complaint=${item.complaint_id}` : "/my-reports"}
                  onClick={() => markRead(item.id)}
                >
                  <span className="notification-dot" />
                  <span><strong>{item.message}</strong><small>{formatDate(item.created_at)}</small></span>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-copy">
        <div className="eyebrow"><span className="live-dot" /> YOUR CITY, A LITTLE BETTER</div>
        <h1>Good things happen<br />when we <span>speak up.</span></h1>
        <p className="hero-description">
          Spot something that needs fixing? Tell us about it. Together, we can make our neighborhoods work better for everyone.
        </p>
        <a className="button button-primary hero-button" href="#report">
          Report a local issue <span aria-hidden="true">↗</span>
        </a>
        <div className="hero-note">
          <span className="avatar-stack" aria-hidden="true">
            <span>R</span><span>M</span><span>A</span>
          </span>
          <span><strong>Small reports. Real change.</strong><br />A more helpful city starts with you.</span>
        </div>
      </div>

      <div className="hero-art" aria-label="Illustration of a greener, more connected neighborhood">
        <div className="sun-disc" />
        <div className="art-cloud cloud-one" /><div className="art-cloud cloud-two" />
        <div className="art-hill hill-back" /><div className="art-hill hill-front" />
        <div className="building building-left"><i /><i /><i /><b /></div>
        <div className="building building-right"><i /><i /><i /><b /></div>
        <div className="house">
          <div className="roof" />
          <div className="house-body"><span className="window" /><span className="door" /><span className="window" /></div>
        </div>
        <div className="tree tree-left"><i /><b /></div>
        <div className="tree tree-right"><i /><b /></div>
        <div className="art-path" />
        <div className="art-label"><span>✳</span> Every voice moves us forward</div>
        <div className="art-pin"><span>✓</span></div>
      </div>
    </section>
  );
}

function ReportForm({ onSubmitted }) {
  const [form, setForm] = useState({ description: "", location: "", language: "auto" });
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState("");
  const [coordinates, setCoordinates] = useState(null);
  const [locationState, setLocationState] = useState("idle");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!photo) {
      setPhotoPreview("");
      return undefined;
    }

    const previewUrl = URL.createObjectURL(photo);
    setPhotoPreview(previewUrl);
    return () => URL.revokeObjectURL(previewUrl);
  }, [photo]);

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
    setError("");
    setSuccess("");
  }

  function selectPhoto(file) {
    if (!file) return;
    setError("");
    setSuccess("");
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Choose a JPG, PNG, or WebP photo.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Photos must be 5 MB or smaller.");
      return;
    }
    setPhoto(file);
  }

  function locateIssue() {
    if (!navigator.geolocation) {
      setLocationState("unsupported");
      return;
    }
    setLocationState("loading");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setCoordinates({ latitude: coords.latitude, longitude: coords.longitude });
        setLocationState("ready");
      },
      () => setLocationState("error"),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = new FormData();
      payload.append("description", form.description);
      payload.append("location", form.location);
      payload.append("language", form.language);
      if (photo) payload.append("photo", photo);
      if (coordinates) {
        payload.append("latitude", String(coordinates.latitude));
        payload.append("longitude", String(coordinates.longitude));
      }

      const response = await fetch(`${API_URL}/complaints`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
        body: payload,
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = result.detail;
        throw new Error(typeof detail === "string" ? detail : "Please check your details and try again.");
      }
      setForm({ description: "", location: "", language: "auto" });
      setPhoto(null);
      setCoordinates(null);
      setLocationState("idle");
      setSuccess(`Your report is in. Reference: ${result.complaint.id.slice(0, 8).toUpperCase()}`);
      onSubmitted();
    } catch (submitError) {
      setError(submitError instanceof TypeError
        ? "We couldn't reach CivicSense. Please check that the service is running and try again."
        : submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="report-card" id="report">
      <div className="card-heading">
        <div>
          <span className="section-kicker">START A REPORT</span>
          <h2>Show us what’s wrong.</h2>
        </div>
        <span className="form-step">01 <span>/ 01</span></span>
      </div>
      <p className="form-intro">A photo and a few details help your community understand what needs attention.</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="description">What’s the issue?</label>
        <textarea
          id="description"
          name="description"
          value={form.description}
          onChange={updateField}
          placeholder="Describe the problem in a few words…"
          minLength={5}
          maxLength={3000}
          required
          rows={3}
        />
        <div className="photo-field">
          <label htmlFor="photo">Add a photo <span className="optional-label">OPTIONAL</span></label>
          {photo && photoPreview ? (
            <div className="photo-preview">
              <img src={photoPreview} alt="Preview of the defect you selected" />
              <div className="photo-preview-info">
                <strong>{photo.name}</strong>
                <span>{(photo.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload</span>
              </div>
              <button
                className="remove-photo"
                type="button"
                onClick={() => setPhoto(null)}
                aria-label="Remove selected photo"
              >
                ×
              </button>
            </div>
          ) : (
            <label
              className="photo-dropzone"
              htmlFor="photo"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                selectPhoto(event.dataTransfer.files[0]);
              }}
            >
              <input
                className="photo-input"
                id="photo"
                name="photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => {
                  selectPhoto(event.currentTarget.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
              <span className="upload-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span className="upload-copy">
                <strong>Choose a photo <span>or drop it here</span></strong>
                <small>JPG, PNG or WebP · Up to 5 MB</small>
              </span>
              <span className="upload-browse">Browse</span>
            </label>
          )}
        </div>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="location">Where is it?</label>
            <div className="input-with-icon">
              <span aria-hidden="true">⌖</span>
              <input
                id="location"
                name="location"
                value={form.location}
                onChange={updateField}
                placeholder="Street, area or landmark"
                minLength={2}
                maxLength={200}
                required
              />
            </div>
            <button className="location-pin-button" type="button" onClick={locateIssue} disabled={locationState === "loading"}>
              {locationState === "loading" ? "Getting location…" : coordinates ? "✓ Map location added" : "⌖ Pin this on the map"}
            </button>
            {locationState === "error" && <span className="location-hint error-text">Location permission was unavailable. You can still submit without a map pin.</span>}
            {locationState === "unsupported" && <span className="location-hint error-text">This browser does not support location pins.</span>}
            {coordinates && <span className="location-hint">Your approximate location will appear on the community map.</span>}
          </div>
          <div className="form-field language-field">
            <label htmlFor="language">Language</label>
            <select id="language" name="language" value={form.language} onChange={updateField}>
              <option value="auto">Auto detect</option>
              <option value="english">English</option>
              <option value="hindi">हिन्दी</option>
              <option value="gujarati">ગુજરાતી</option>
            </select>
          </div>
        </div>
        {error && <p className="form-message error-message" role="alert">{error}</p>}
        {success && <p className="form-message success-message" role="status">{success}</p>}
        <button className="button button-dark submit-button" type="submit" disabled={submitting}>
          {submitting ? "Sending your report…" : "Submit report"}
          {!submitting && <span aria-hidden="true">↗</span>}
        </button>
        <p className="privacy-note"><span aria-hidden="true">♢</span> Your photo is shared with this public report.</p>
      </form>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="how-section" id="how-it-works">
      <div className="section-heading">
        <div>
          <span className="section-kicker">A BETTER CITY, TOGETHER</span>
          <h2>It starts with a simple report.</h2>
        </div>
        <p>No paperwork. No runaround. Just a straightforward way to bring local issues to light.</p>
      </div>
      <div className="steps">
        <article className="step">
          <span className="step-number">01</span>
          <span className="step-icon peach">✎</span>
          <h3>Tell us what you see</h3>
          <p>Describe the issue and where it’s happening. Share it in English, Hindi, or Gujarati.</p>
        </article>
        <article className="step">
          <span className="step-number">02</span>
          <span className="step-icon lime">⌕</span>
          <h3>We’ll get it noticed</h3>
          <p>Your report gives the community a clearer picture of what needs attention.</p>
        </article>
        <article className="step">
          <span className="step-number">03</span>
          <span className="step-icon blue">↗</span>
          <h3>Progress starts here</h3>
          <p>Every issue surfaced is a step toward a safer, cleaner, more welcoming neighborhood.</p>
        </article>
      </div>
    </section>
  );
}

function MapBounds({ reports }) {
  const map = useMap();
  useEffect(() => {
    const points = reports
      .filter((report) => Number.isFinite(report.latitude) && Number.isFinite(report.longitude))
      .map((report) => [report.latitude, report.longitude]);
    if (points.length > 1) map.fitBounds(points, { padding: [30, 30], maxZoom: 14 });
    else if (points.length === 1) map.setView(points[0], 14);
    else map.setView([23.2156, 72.6369], 12);
  }, [map, reports]);
  return null;
}

function CivicMap({ reports }) {
  const mappedReports = reports.filter(
    (report) => Number.isFinite(report.latitude) && Number.isFinite(report.longitude),
  );
  const center = mappedReports.length
    ? [mappedReports[0].latitude, mappedReports[0].longitude]
    : [23.2156, 72.6369];

  return (
    <div className="community-map" aria-label="Map of reported civic issues">
      <MapContainer center={center} zoom={12} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapBounds reports={mappedReports} />
        {mappedReports.map((report) => (
          <Marker key={report.id} position={[report.latitude, report.longitude]} icon={mapMarkerIcon}>
            <Popup>
              <strong>{report.description}</strong>
              <br />
              {report.location}
              <br />
              <span>{statusLabel(report.status)} · {report.support_count || 0} neighbors support</span>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      {mappedReports.length === 0 && (
        <div className="map-empty-note">Reports with a map pin will appear here. Add one when you submit an issue.</div>
      )}
    </div>
  );
}

function Community({ refreshKey }) {
  const [reports, setReports] = useState([]);
  const [resolvedReports, setResolvedReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [filters, setFilters] = useState({ search: "", location: "", category: "", status: "", created_after: "", created_before: "" });
  const [appliedFilters, setAppliedFilters] = useState(filters);
  const [visibleCount, setVisibleCount] = useState(8);

  useEffect(() => {
    let cancelled = false;
    const queryFilters = { ...appliedFilters };
    if (queryFilters.created_before) {
      const [year, month, day] = queryFilters.created_before.split("-").map(Number);
      const beforeExclusive = new Date(Date.UTC(year, month - 1, day + 1));
      queryFilters.created_before = beforeExclusive.toISOString().slice(0, 10);
    }
    const query = new URLSearchParams(Object.entries(queryFilters).filter(([, value]) => value));
    setLoading(true);
    setLoadError("");
    Promise.all([
      fetch(`${API_URL}/community/complaints?${query}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      }),
      fetch(`${API_URL}/community/complaints?status=resolved`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      }),
    ])
      .then(async ([response, resolvedResponse]) => {
        const [result, resolvedResult] = await Promise.all([response.json(), resolvedResponse.json()]);
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Community reports are unavailable.");
        if (!resolvedResponse.ok) throw new Error(typeof resolvedResult.detail === "string" ? resolvedResult.detail : "Resolved reports are unavailable.");
        if (!cancelled) {
          setReports(result.complaints);
          setResolvedReports(resolvedResult.complaints.slice(0, 3));
        }
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof TypeError
          ? "Community reports are temporarily unavailable."
          : error.message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [appliedFilters, refreshKey]);

  function updateFilter(event) {
    setFilters((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function clearFilters() {
    const cleared = { search: "", location: "", category: "", status: "", created_after: "", created_before: "" };
    setFilters(cleared);
    setAppliedFilters(cleared);
  }

  return (
    <section className="community-section" id="community">
      <div className="community-top">
        <div>
          <span className="section-kicker">YOUR NEIGHBORHOOD</span>
          <h2>Better, bit by bit.</h2>
        </div>
        <a className="text-link" href="/#report">Have something to share? <span>↗</span></a>
      </div>
      <div className="category-grid">
        {categories.map((category) => (
          <a className="category-card" href="/#report" key={category.title}>
            <span className={`category-icon ${category.color}`} aria-hidden="true">{category.icon}</span>
            <span className="category-title">{category.title}</span>
            <span className="category-detail">{category.detail}</span>
            <span className="category-arrow" aria-hidden="true">↗</span>
          </a>
        ))}
      </div>

      <div className="community-tools">
        <div className="community-section-heading">
          <div><span className="section-kicker">THE COMMUNITY MAP</span><h3>Issues around you</h3></div>
          <span className="map-pin-privacy">Pins are optional and only added with your permission.</span>
        </div>
        <CivicMap reports={reports} />
      </div>

      {resolvedReports.length > 0 && (
        <div className="resolved-section">
          <div className="community-section-heading">
            <div><span className="section-kicker">PROGRESS WORTH CELEBRATING</span><h3>Recently resolved</h3></div>
            <span className="resolved-count">{resolvedReports.length} resolved</span>
          </div>
          <div className="resolved-grid">
            {resolvedReports.map((report) => (
              <article className="resolved-card" key={report.id}>
                <span className="resolved-check" aria-hidden="true">✓</span>
                <div><h4>{report.description}</h4><p>⌖ {report.location}</p></div>
                <time dateTime={report.created_at}>{formatDate(report.created_at)}</time>
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="reports-heading community-reports-heading">
        <div><span className="section-kicker">COMMUNITY VOICES</span><h3>Explore reports</h3></div>
        {!loading && !loadError && <span className="report-count">{reports.length} {reports.length === 1 ? "report" : "reports"}</span>}
      </div>
      <form className="community-filters" onSubmit={(event) => { event.preventDefault(); setVisibleCount(8); setAppliedFilters(filters); }}>
        <label className="sr-only" htmlFor="filter-search">Search reports</label>
        <input id="filter-search" name="search" value={filters.search} onChange={updateFilter} placeholder="Search issues…" />
        <label className="sr-only" htmlFor="filter-location">Filter by neighborhood</label>
        <input id="filter-location" name="location" value={filters.location} onChange={updateFilter} placeholder="Neighborhood" />
        <label className="sr-only" htmlFor="filter-category">Filter by category</label>
        <select id="filter-category" name="category" value={filters.category} onChange={updateFilter}>
          <option value="">All issue types</option>
          {issueTypes.slice(0, -1).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="sr-only" htmlFor="filter-status">Filter by status</label>
        <select id="filter-status" name="status" value={filters.status} onChange={updateFilter}>
          <option value="">All statuses</option>
          <option value="pending">Awaiting review</option>
          <option value="approved">Approved</option>
          <option value="declined">Declined</option>
          <option value="resolved">Resolved</option>
        </select>
        <label className="sr-only" htmlFor="filter-created-after">From date</label>
        <input id="filter-created-after" name="created_after" type="date" value={filters.created_after} onChange={updateFilter} aria-label="From date" />
        <label className="sr-only" htmlFor="filter-created-before">Through date</label>
        <input id="filter-created-before" name="created_before" type="date" value={filters.created_before} onChange={updateFilter} aria-label="Through date" />
        <button className="button button-dark" type="submit">Search <span aria-hidden="true">⌕</span></button>
        <button className="filter-clear" type="button" onClick={clearFilters}>Clear</button>
      </form>
      {loading ? (
        <p className="report-state">Loading community reports…</p>
      ) : loadError ? (
        <p className="report-state error-message" role="alert">{loadError}</p>
      ) : reports.length === 0 ? (
        <div className="empty-reports"><span aria-hidden="true">✳</span><p>No reports match these filters.</p><button type="button" onClick={clearFilters}>Clear filters</button></div>
      ) : (
        <>
          <div className="dashboard-report-list community-report-list">
            {reports.slice(0, visibleCount).map((report) => (
              <ReportCard key={report.id} report={report} community />
            ))}
          </div>
          {reports.length > visibleCount && (
            <button className="load-more-button" type="button" onClick={() => setVisibleCount((count) => count + 8)}>
              Show more reports
            </button>
          )}
        </>
      )}
    </section>
  );
}

function formatDate(date) {
  const parsed = new Date(date);
  return Number.isNaN(parsed.getTime())
    ? ""
    : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(parsed);
}

function statusLabel(status) {
  return {
    pending: "Awaiting review",
    approved: "Approved",
    declined: "Declined",
    resolved: "Resolved",
  }[status] || status;
}

function ReportCard({ report, admin = false, community = false, onReview, reviewing }) {
  const [timeline, setTimeline] = useState([]);
  const [updates, setUpdates] = useState([]);
  const [threadOpen, setThreadOpen] = useState(false);
  const [threadLoading, setThreadLoading] = useState(false);
  const [updateText, setUpdateText] = useState("");
  const [threadError, setThreadError] = useState("");
  const [submittingUpdate, setSubmittingUpdate] = useState(false);
  const [supported, setSupported] = useState(Boolean(report.viewer_has_supported));
  const [supportCount, setSupportCount] = useState(report.support_count || 0);
  const [triage, setTriage] = useState({
    category: report.category || "unclassified",
    department: report.department || "",
    priority: report.priority || "normal",
    response_hours: 48,
    decline_reason: "",
  });
  const [triageMessage, setTriageMessage] = useState("");

  useEffect(() => {
    setTriage((current) => ({
      ...current,
      category: report.category || "unclassified",
      department: report.department || "",
      priority: report.priority || "normal",
    }));
  }, [report.category, report.department, report.priority]);

  async function loadThread() {
    setThreadLoading(true);
    setThreadError("");
    try {
      const headers = { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` };
      const [timelineResponse, updatesResponse] = await Promise.all([
        fetch(`${API_URL}/community/complaints/${report.id}/timeline`, { headers }),
        fetch(`${API_URL}/community/complaints/${report.id}/updates`, { headers }),
      ]);
      const [timelineResult, updatesResult] = await Promise.all([timelineResponse.json(), updatesResponse.json()]);
      if (!timelineResponse.ok) throw new Error(typeof timelineResult.detail === "string" ? timelineResult.detail : "Timeline unavailable.");
      if (!updatesResponse.ok) throw new Error(typeof updatesResult.detail === "string" ? updatesResult.detail : "Updates unavailable.");
      setTimeline(timelineResult.events);
      setUpdates(updatesResult.updates);
    } catch (error) {
      setThreadError(error instanceof TypeError ? "Could not load this report’s updates." : error.message);
    } finally {
      setThreadLoading(false);
    }
  }

  async function toggleThread() {
    const nextOpen = !threadOpen;
    setThreadOpen(nextOpen);
    if (nextOpen) await loadThread();
  }

  async function postUpdate(event) {
    event.preventDefault();
    setSubmittingUpdate(true);
    setThreadError("");
    try {
      const response = await fetch(`${API_URL}/community/complaints/${report.id}/updates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("civicsense_token")}`,
        },
        body: JSON.stringify({ body: updateText }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not post update.");
      setUpdateText("");
      await loadThread();
    } catch (error) {
      setThreadError(error instanceof TypeError ? "Could not post your update. Try again." : error.message);
    } finally {
      setSubmittingUpdate(false);
    }
  }

  async function toggleSupport() {
    try {
      const response = await fetch(`${API_URL}/community/complaints/${report.id}/support`, {
        method: supported ? "DELETE" : "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not update support.");
      setSupported(result.supported);
      setSupportCount(result.support_count);
    } catch (error) {
      setThreadError(error instanceof TypeError ? "Could not update support. Try again." : error.message);
    }
  }

  async function saveTriage(status) {
    const body = { ...triage };
    if (!body.department) delete body.department;
    if (!body.decline_reason) delete body.decline_reason;
    if (status) body.status = status;
    setTriageMessage("");
    try {
      await onReview(report.id, body);
      setTriageMessage(status === "declined" ? "Report declined with reason." : status ? `Report ${status}.` : "Triage details saved.");
    } catch (error) {
      setTriageMessage(error.message);
    }
  }

  return (
    <article className="dashboard-report">
      {report.photo_url && (
        <img
          className="dashboard-report-photo"
          src={`${API_URL}${report.photo_url}`}
          alt={`Photo for report: ${report.description}`}
        />
      )}
      <div className="dashboard-report-main">
        <div className="dashboard-report-heading">
          <span className={`dashboard-status status-${report.status}`}>
            <span className="status-indicator" />
            {statusLabel(report.status)}
          </span>
          <time dateTime={report.created_at}>{formatDate(report.created_at)}</time>
        </div>
        <h3>{report.description}</h3>
        <p className="dashboard-report-location"><span aria-hidden="true">⌖</span> {report.location}</p>
        <div className="report-meta-row">
          {report.priority && report.priority !== "normal" && <span className={`priority-tag priority-${report.priority}`}>{report.priority} priority</span>}
          {report.department && <span className="department-tag">{report.department}</span>}
          {report.response_due_at && (
            <span className={`response-target${new Date(report.response_due_at) < new Date() && report.status !== "resolved" ? " target-overdue" : ""}`}>
              Target: {formatDate(report.response_due_at)}
              {new Date(report.response_due_at) < new Date() && report.status !== "resolved" ? " · overdue" : ""}
            </span>
          )}
          {report.status === "resolved" && report.resolved_at && <span className="resolved-on">Resolved {formatDate(report.resolved_at)}</span>}
        </div>
        {admin && (
          <p className="dashboard-reporter">Submitted by {report.reporter_name} · {report.reporter_email}</p>
        )}
        {report.decline_reason && <p className="status-explanation decline-explanation"><strong>Review note:</strong> {report.decline_reason}</p>}
        {report.status === "approved" && !admin && (
          <p className="status-explanation">Your report has been approved and is ready for follow-up.</p>
        )}
        {community && (
          <div className="report-community-actions">
            <button className={`support-button${supported ? " is-supported" : ""}`} type="button" onClick={toggleSupport}>
              <span aria-hidden="true">♡</span> {supported ? "Supported" : "Support"} <strong>{supportCount}</strong>
            </button>
            {threadError && !threadOpen && <p className="thread-error" role="alert">{threadError}</p>}
          </div>
        )}
        <button className="thread-toggle owner-thread-toggle" type="button" onClick={toggleThread} aria-expanded={threadOpen}>
          {threadOpen ? "Hide updates & timeline" : "Updates & timeline"}
        </button>
        {admin && (
          <div className="admin-triage">
            <div className="triage-grid">
              <label>Issue category
                <select value={triage.category} onChange={(event) => setTriage((value) => ({ ...value, category: event.target.value }))}>
                  <option value="unclassified">Choose category</option>
                  {issueTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>Assigned department
                <select value={triage.department} onChange={(event) => setTriage((value) => ({ ...value, department: event.target.value }))}>
                  <option value="">Unassigned</option>
                  {departments.map((department) => <option key={department} value={department}>{department}</option>)}
                </select>
              </label>
              <label>Priority
                <select value={triage.priority} onChange={(event) => setTriage((value) => ({ ...value, priority: event.target.value }))}>
                  {["low", "normal", "high", "urgent"].map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
                </select>
              </label>
              <label>Response target
                <select value={triage.response_hours} onChange={(event) => setTriage((value) => ({ ...value, response_hours: Number(event.target.value) }))}>
                  <option value={24}>24 hours</option><option value={48}>48 hours</option><option value={72}>3 days</option><option value={168}>1 week</option>
                </select>
              </label>
            </div>
            {report.status === "pending" && (
              <label className="decline-reason-field">Reason (required to decline)
                <textarea value={triage.decline_reason} maxLength={1000} onChange={(event) => setTriage((value) => ({ ...value, decline_reason: event.target.value }))} placeholder="Explain the decision for the reporter…" />
              </label>
            )}
            {triageMessage && <p className="triage-message" role="status">{triageMessage}</p>}
            <div className="review-actions">
              <button className="review-button save-triage-button" type="button" disabled={reviewing} onClick={() => saveTriage()}>
                Save triage
              </button>
              {report.status === "pending" && (
                <>
                  <button className="review-button approve-button" type="button" disabled={reviewing} onClick={() => saveTriage("approved")}>Approve</button>
                  <button className="review-button decline-button" type="button" disabled={reviewing} onClick={() => saveTriage("declined")}>Decline</button>
                </>
              )}
              {report.status === "approved" && (
                <button className="review-button approve-button" type="button" disabled={reviewing} onClick={() => saveTriage("resolved")}>Mark resolved</button>
              )}
            </div>
          </div>
        )}
        {threadOpen && (
          <div className="report-thread">
            {threadLoading ? <p className="thread-state">Loading updates…</p> : threadError && <p className="thread-error" role="alert">{threadError}</p>}
            <section className="thread-updates">
              <h4>Community updates</h4>
              {updates.length === 0 ? <p className="thread-state">No updates yet. Add helpful information for your neighbors.</p> : updates.map((update) => (
                <article className="thread-comment" key={update.id}>
                  <div><strong>{update.author_name}</strong><time dateTime={update.created_at}>{formatDate(update.created_at)}</time></div>
                  <p>{update.body}</p>
                </article>
              ))}
              {report.status !== "resolved" && report.status !== "declined" && (
                <form className="thread-form" onSubmit={postUpdate}>
                  <label className="sr-only" htmlFor={`update-${report.id}`}>Add an update</label>
                  <textarea id={`update-${report.id}`} value={updateText} maxLength={1000} minLength={3} onChange={(event) => setUpdateText(event.target.value)} placeholder="Share a useful update…" required />
                  <button className="review-button save-triage-button" type="submit" disabled={submittingUpdate}>{submittingUpdate ? "Posting…" : "Post update"}</button>
                </form>
              )}
            </section>
            <section className="thread-timeline">
              <h4>Report timeline</h4>
              {timeline.map((event) => (
                <div className="timeline-event" key={event.id}>
                  <span />
                  <div><strong>{event.message}</strong><small>{event.actor_name || "CivicSense"} · {formatDate(event.created_at)}</small></div>
                </div>
              ))}
            </section>
          </div>
        )}
      </div>
    </article>
  );
}

function AuthLoading() {
  return (
    <main className="auth-loading" role="status">
      <span className="brand-icon" aria-hidden="true">✳</span>
      <p>Checking your CivicSense session…</p>
    </main>
  );
}

function DashboardShell({ currentUser, onSignOut, children }) {
  return (
    <>
      <Header currentUser={currentUser} onSignOut={onSignOut} />
      <main className="dashboard-shell">
        <a className="dashboard-back-link" href="/">← CivicSense home</a>
        {children}
      </main>
      <footer className="site-footer">
        <div className="footer-inner">
          <BrandMark />
          <span>Made for the places we call home.</span>
          <span>© 2026 CivicSense</span>
        </div>
      </footer>
    </>
  );
}

function MyReportsPage({ currentUser, onSignOut }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/complaints`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not load your reports.");
        setReports(result.complaints);
      })
      .catch((loadError) => setError(loadError instanceof TypeError
        ? "We couldn’t connect to CivicSense. Please try again."
        : loadError.message))
      .finally(() => setLoading(false));
  }, []);

  const pending = reports.filter((report) => report.status === "pending").length;
  const approved = reports.filter((report) => report.status === "approved").length;
  const declined = reports.filter((report) => report.status === "declined").length;

  return (
    <DashboardShell currentUser={currentUser} onSignOut={onSignOut}>
      <section className="dashboard-heading">
        <span className="section-kicker">YOUR CIVICSENSE ACCOUNT</span>
        <h1>Your reports, in one place.</h1>
        <p>See what you’ve submitted and check each report’s review status.</p>
      </section>
      <div className="report-summary">
        <div><span>Total reports</span><strong>{reports.length}</strong></div>
        <div><span>Awaiting review</span><strong>{pending}</strong></div>
        <div><span>Approved</span><strong>{approved}</strong></div>
        <div><span>Declined</span><strong>{declined}</strong></div>
      </div>
      <div className="dashboard-list-heading">
        <div><span className="section-kicker">YOUR SUBMISSIONS</span><h2>My reports</h2></div>
        <a className="button button-dark" href="/#report">Submit a report <span aria-hidden="true">↗</span></a>
      </div>
      {loading ? (
        <p className="dashboard-state">Loading your reports…</p>
      ) : error ? (
        <p className="dashboard-state error-message" role="alert">{error}</p>
      ) : reports.length === 0 ? (
        <div className="dashboard-empty">
          <span aria-hidden="true">✳</span>
          <h3>No reports yet</h3>
          <p>When you report a local issue, its status and updates will appear here.</p>
          <a className="button button-dark" href="/#report">Report your first issue <span aria-hidden="true">↗</span></a>
        </div>
      ) : (
        <div className="dashboard-report-list">
          {reports.map((report) => <ReportCard key={report.id} report={report} />)}
        </div>
      )}
    </DashboardShell>
  );
}

function AdminPage({ currentUser, onSignOut }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewingId, setReviewingId] = useState("");
  const [filters, setFilters] = useState({ search: "", status: "", priority: "", department: "" });
  const [appliedFilters, setAppliedFilters] = useState(filters);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams(Object.entries(appliedFilters).filter(([, value]) => value));
      const response = await fetch(`${API_URL}/admin/complaints?${query}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("civicsense_token")}` },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not load the review queue.");
      setReports(result.complaints);
    } catch (loadError) {
      setError(loadError instanceof TypeError
        ? "We couldn’t connect to CivicSense. Please try again."
        : loadError.message);
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => { loadReports(); }, [loadReports]);

  async function reviewReport(id, body) {
    setReviewingId(id);
    setError("");
    try {
      const response = await fetch(`${API_URL}/admin/complaints/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("civicsense_token")}`,
        },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not update this report.");
      setReports((current) => current.map((report) => report.id === id ? { ...report, ...result.complaint } : report));
      return result.complaint;
    } catch (reviewError) {
      setError(reviewError instanceof TypeError
        ? "We couldn’t connect to CivicSense. Please try again."
        : reviewError.message);
      throw reviewError;
    } finally {
      setReviewingId("");
    }
  }

  const pending = reports.filter((report) => report.status === "pending").length;

  return (
    <DashboardShell currentUser={currentUser} onSignOut={onSignOut}>
      <section className="dashboard-heading">
        <span className="section-kicker">CIVICSENSE ADMIN</span>
        <h1>Complaint review queue.</h1>
        <p>Review submitted reports and approve them for follow-up or decline them.</p>
      </section>
      <div className="admin-queue-summary">
        <span>{reports.length} total reports</span>
        <strong>{pending} awaiting review</strong>
      </div>
      <form className="admin-filters" onSubmit={(event) => { event.preventDefault(); setAppliedFilters(filters); }}>
        <label className="sr-only" htmlFor="admin-search">Search complaint queue</label>
        <input id="admin-search" name="search" value={filters.search} onChange={(event) => setFilters((value) => ({ ...value, search: event.target.value }))} placeholder="Search report, location or email…" />
        <label className="sr-only" htmlFor="admin-status">Filter by status</label>
        <select id="admin-status" value={filters.status} onChange={(event) => setFilters((value) => ({ ...value, status: event.target.value }))}>
          <option value="">All statuses</option><option value="pending">Awaiting review</option><option value="approved">Approved</option><option value="declined">Declined</option><option value="resolved">Resolved</option>
        </select>
        <label className="sr-only" htmlFor="admin-priority">Filter by priority</label>
        <select id="admin-priority" value={filters.priority} onChange={(event) => setFilters((value) => ({ ...value, priority: event.target.value }))}>
          <option value="">All priorities</option><option value="urgent">Urgent</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option>
        </select>
        <label className="sr-only" htmlFor="admin-department">Filter by department</label>
        <select id="admin-department" value={filters.department} onChange={(event) => setFilters((value) => ({ ...value, department: event.target.value }))}>
          <option value="">All departments</option>{departments.map((department) => <option key={department} value={department}>{department}</option>)}
        </select>
        <button className="review-button save-triage-button" type="submit">Apply filters</button>
        <button className="filter-clear" type="button" onClick={() => { const cleared = { search: "", status: "", priority: "", department: "" }; setFilters(cleared); setAppliedFilters(cleared); }}>Clear</button>
      </form>
      {error && <p className="dashboard-state error-message" role="alert">{error}</p>}
      {loading ? (
        <p className="dashboard-state">Loading the review queue…</p>
      ) : reports.length === 0 ? (
        <div className="dashboard-empty"><span aria-hidden="true">✓</span><h3>All clear for now</h3><p>There are no reports in the review queue yet.</p></div>
      ) : (
        <div className="dashboard-report-list">
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              admin
              onReview={reviewReport}
              reviewing={reviewingId === report.id}
            />
          ))}
        </div>
      )}
    </DashboardShell>
  );
}

function AccessDenied({ currentUser, onSignOut }) {
  return (
    <DashboardShell currentUser={currentUser} onSignOut={onSignOut}>
      <section className="dashboard-empty access-denied">
        <span aria-hidden="true">⌑</span>
        <h1>Admin access only</h1>
        <p>Your account doesn’t have permission to review reports.</p>
        <a className="button button-dark" href="/">Back to CivicSense</a>
      </section>
    </DashboardShell>
  );
}

export default function App() {
  const [communityRefresh, setCommunityRefresh] = useState(0);
  const [authState, setAuthState] = useState(
    () => localStorage.getItem("civicsense_token") ? "checking" : "unauthenticated",
  );
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("civicsense_token");
    if (!token) {
      setAuthState("unauthenticated");
      return;
    }
    fetch(`${API_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => {
        if (!response.ok) throw new Error("Session expired");
        const result = await response.json();
        setCurrentUser(result.user);
        localStorage.setItem("civicsense_user", JSON.stringify(result.user));
        setAuthState("authenticated");
      })
      .catch(() => {
        localStorage.removeItem("civicsense_token");
        localStorage.removeItem("civicsense_user");
        setCurrentUser(null);
        setAuthState("unauthenticated");
      });
  }, []);

  function signOut() {
    localStorage.removeItem("civicsense_token");
    localStorage.removeItem("civicsense_user");
    setCurrentUser(null);
    setAuthState("unauthenticated");
  }

  const pathname = window.location.pathname;
  if (pathname === "/login" || pathname === "/register") {
    if (authState === "authenticated") {
      window.location.replace("/");
      return <AuthLoading />;
    }
    return <AuthPage mode={pathname === "/register" ? "register" : "login"} />;
  }
  if (authState === "checking") return <AuthLoading />;
  if (authState !== "authenticated") {
    window.location.replace("/login");
    return <AuthLoading />;
  }

  if (pathname === "/my-reports") {
    return <MyReportsPage currentUser={currentUser} onSignOut={signOut} />;
  }
  if (pathname === "/admin") {
    if (!currentUser?.is_admin) return <AccessDenied currentUser={currentUser} onSignOut={signOut} />;
    return <AdminPage currentUser={currentUser} onSignOut={signOut} />;
  }

  return (
    <>
      <Header currentUser={currentUser} onSignOut={signOut} />
      <main>
        <div className="page-shell">
          <div className="hero-layout">
            <Hero />
            <ReportForm onSubmitted={() => setCommunityRefresh((value) => value + 1)} />
          </div>
          <HowItWorks />
          <Community refreshKey={communityRefresh} />
          <section className="closing-cta">
            <div className="closing-mark" aria-hidden="true">✳</div>
            <div>
              <span className="section-kicker">YOUR VOICE MATTERS</span>
              <h2>Let’s make this place<br />a little more <em>ours.</em></h2>
            </div>
            <a className="button button-dark" href="#report">Share what you see <span aria-hidden="true">↗</span></a>
          </section>
        </div>
      </main>
      <footer className="site-footer">
        <div className="footer-inner">
          <BrandMark />
          <span>Made for the places we call home.</span>
          <span>© 2026 CivicSense</span>
        </div>
      </footer>
    </>
  );
}
