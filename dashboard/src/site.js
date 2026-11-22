// Everything the landing page says about who made this, in one editable place.
//
// Nothing here is invented. The team's names, roles, sections and photographs
// are the ones the team supplied.
// The institution logo comes from the university's website.
//
// To add a photograph: put the file in dashboard/public/ (for example
// dashboard/public/team/member1.jpg) and write its path here relative to that
// folder ("team/member1.jpg"). Then `npm run build`. A path that is set but
// missing would show a broken image, so leave a value null until the file exists.
//
// Identity for the submitted documents lives in scripts/synopsis_content.py;
// keep the two in step by hand when you fill this in.

export const SITE = {
  title: "Smart Traffic Management System",
  short: "STMS",
  model: "MFSTNet",
  // What the system does, worded to match what is built: it monitors and forecasts
  // traffic, and signal control is studied in simulation, never applied to a real signal (P97a).
  tagline: "Intelligent traffic monitoring, forecasting and signal-control research",
  description:
    "A camera-based system that counts vehicles lane by lane, forecasts the next minute of traffic at an " +
    "intersection, and studies reinforcement-learning signal control in simulation, built and measured " +
    "as a final-year B.Tech CSE (ML/AI) major project.",
  institution: {
    name: "Graphic Era Hill University",
    department: "Department of Computer Science and Engineering (ML/AI)",
    logo: "brand/university-wordmark.svg",
  },
  campusPhoto: null,
  repository: "https://github.com/Divyansh-9/CNN_VIT_BILSTM_CROSS_ATTENTION_BASED_TRAFFIC_MANAGEMENT_SYSTEM",
  // Exactly four members, as the team supplied them on 2026-11-13. The roles are
  // the team's own "temporary" roles; edit them here when they are final.
  // Photographs were matched to names by the order they were sent in. If two are
  // swapped, swap the `photo` values.
  team: [
    { name: "Divyansh Uniyal", role: "Project Lead & System Integration", section: "ML2", lead: true,
      contribution: "Project leadership and integration across the system.",
      photo: "team/divyansh-uniyal-uniform.webp", photoPosition: "center top", linkedin: null, github: null },
    { name: "Abhishek Negi", role: "Frontend Development & Dashboard Design", section: "C1", lead: false,
      contribution: "Frontend development and dashboard design.",
      photo: "team/abhishek-negi-uniform.webp", photoPosition: "center top", linkedin: null, github: null },
    { name: "Km Shivani", role: "Computer Vision & YOLO Vehicle Detection", section: "ML2", lead: false,
      contribution: "Computer vision and YOLO-based vehicle detection.",
      photo: "team/km-shivani-uniform.webp", photoPosition: "center top", linkedin: null, github: null },
    { name: "Bhavya Gogia", role: "Backend Integration & Testing", section: "C1", lead: false,
      contribution: "Backend integration and system testing.",
      photo: "team/bhavya-gogia-uniform.webp", photoPosition: "center top", linkedin: null, github: null },
  ],
};

// A path under dashboard/public/, resolved against wherever the page is served
// (/dashboard/ on the server, / in a bare dev server).
export function asset(path) {
  const base = (typeof import.meta !== "undefined" && import.meta.env?.BASE_URL) || "/";
  return `${base}${String(path).replace(/^\//, "")}`;
}
