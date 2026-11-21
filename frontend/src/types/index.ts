// ─── Core Ticket (matches backend /tickets response exactly) ─────────────────
export interface Ticket {
  id: number;
  category: string;
  lat: number;
  lng: number;
  severity: number;
  status: 'open' | 'assigned' | 'in_progress' | 'needs_review' | 'resolved' | 'reopened';
  reporter_count: number;
  priority: number;
  priority_reasons: string[];
  ward_id?: number;
  assigned_officer_id?: number;
  escalation_level: number;
  created_at: string;
  sla_deadline: string;
  clock_stopped: boolean;
  clock_stop_reason?: string;
  before_image: string;
  after_image?: string;
  verification_score?: number;
  verification_details?: VerificationDetails;
  is_repeat_defect: boolean;
  original_ticket_id?: number;
  citizen_verified?: boolean;
  citizen_feedback?: string;
  reopened_count: number;
  is_duplicate?: boolean;
  events?: Event[];
  contractor_info?: ContractorInfo | null;
}

export interface VerificationDetails {
  location_ok: boolean;
  scene_match_ok: boolean;
  defect_check_ok: boolean;
  verification_score: number;
  passed_checks: number;
  total_checks: number;
  distance_m: number;
  allowed_distance_m: number;
  orb_matches: number;
  required_matches: number;
  structural_similarity: number;
  defect_still_visible: boolean;
}

// ─── Event (matches backend events table exactly) ────────────────────────────
export interface Event {
  id: number;
  ticket_id: number;
  kind: string;
  detail: string;
  officer_id?: number;
  at: string;
  event_metadata?: any;
}

// ─── Ward scores (matches /wards/scores API exactly) ─────────────────────────
export interface WardMetrics {
  total_tickets: number;
  resolved: number;
  resolution_rate: number;
  citizen_verified_rate: number;
  avg_resolution_hours: number;
  overdue: number;
  reopened: number;
  reopen_rate: number;
}

export interface WardScore {
  ward_id: number;
  ward_name: string;
  ward_number: number;
  metrics: WardMetrics;
}

// ─── System stats (matches /stats API exactly) ────────────────────────────────
export interface SystemStats {
  total_tickets: number;
  resolved: number;
  resolution_rate: number;
  needs_review: number;
  overdue: number;
  repeat_defects: number;
  categories: string[];
}

// ─── Contractor info ──────────────────────────────────────────────────────────
export interface ContractorInfo {
  contractor: {
    id: number;
    name: string;
    registration_number: string;
    contact_person: string;
    phone: string;
    is_blacklisted: boolean;
  };
  work_order: {
    id: number;
    completion_date: string;
    warranty_months: number;
    in_warranty: boolean;
    cost: number;
  };
  original_ticket: {
    id: number;
    created_at: string;
    resolved_at: string;
    before_image: string;
    after_image: string;
  };
}

export type CategoryType = 'pothole' | 'streetlight' | 'water_leak' | 'garbage' | 'live_wire';

export interface ReportFormData {
  image: File;
  lat: number;
  lng: number;
  category_hint: CategoryType;
}

export interface ResolutionFormData {
  image: File;
  lat: number;
  lng: number;
  accuracy_m: number;
  officer_id: number;
}
