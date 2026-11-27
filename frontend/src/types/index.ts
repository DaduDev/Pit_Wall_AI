export interface User {
  id: string;
  email: string;
  display_name: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

export interface A2AHop {
  agent_name: string;
  endpoint: string;
  duration_ms: number;
  dataset_id?: string;
  status: 'success' | 'error';
  error?: string;
}

export interface WebSource {
  title: string;
  url: string;
}

export interface WebIntelligenceCardData {
  title: string;
  summary: string;
  bullets?: string[];
  sources: WebSource[];
  grounded?: boolean;
  provider?: 'gemini' | 'ollama_fallback' | 'cache' | string;
}

export interface KpiMetric {
  label: string;
  value: string;
}

export interface KpiCardData {
  subtitle?: string;
  metrics: KpiMetric[];
}

export interface DataTableData {
  subtitle?: string;
  columns: string[];
  rows: Record<string, any>[];
}

export interface EngineeringTrace {
  data_domain: 'historical' | 'telemetry' | 'mixed' | 'research';
  query?: string;
  execution_time_ms?: number;
  row_count?: number;
  dataset_id?: string;
  a2a_hops?: A2AHop[];
  grounding_sources?: WebSource[];
  grounded?: boolean;
  provider?: 'gemini' | 'ollama_fallback' | 'cache' | string;
  telemetry_params?: {
    year?: number;
    grand_prix?: string;
    session_type?: string;
    session_key?: number;
    drivers?: string[];
    driver_numbers?: (number | string)[] | Record<string, number | string>;
    lap_numbers?: (number | string)[] | Record<string, number | string>;
    turn_number?: number;
    corner_nickname?: string;
    slice_range_m?: number[];
    apex_distance_m?: number;
    sector_boundaries_m?: number[];
    circuit_length_m?: number;
    grid_resolution_m?: number;
    interpolation_method?: string;
  };
  strategy_params?: {
    year?: number;
    grand_prix?: string;
    session_type?: string;
    session_key?: number;
    drivers?: string[];
    driver_numbers?: Record<string, number | string>;
    stint_counts?: Record<string, number>;
    clean_lap_counts?: Record<string, number>;
    excluded_lap_counts?: Record<string, number>;
    pit_stop_laps?: Record<string, number[]>;
    [key: string]: unknown;
  } | Record<string, unknown>;
  interpolated_points?: number;
  confidence: number;
  notes?: string;
  [key: string]: unknown;
}

export interface StandardizedDriverMeta {
  code: string;
  name?: string;
  color?: string;
  compound?: string;
}

export interface SectorSplit {
  driver_a?: number;
  driver_b?: number;
  delta_s?: number;
  faster?: string;
  boundary_m?: number;
}

export interface SpeedTrapData {
  driver_a?: number;
  driver_b?: number;
  delta_kph?: number;
  max_speed_a?: number;
  max_speed_b?: number;
}

export interface LapTimesSummary {
  driver_a?: number;
  driver_b?: number;
  delta_s?: number;
  faster?: string;
}

export interface SectorSummary {
  sectors?: {
    sector_1?: SectorSplit;
    sector_2?: SectorSplit;
    sector_3?: SectorSplit;
  };
  speed_trap?: SpeedTrapData;
  lap_times?: LapTimesSummary;
}

export interface ChartMetadata {
  domain?: 'historical' | 'historical_sql' | 'telemetry' | 'mixed' | 'research';
  year?: number;
  grand_prix?: string;
  session_name?: string;
  mode_label?: string;
  drivers?: (StandardizedDriverMeta | string)[];
  track_status?: string | null;
  sector_summary?: SectorSummary | null;
  event_name?: string;
  session_type?: string;
  driver_numbers?: (number | string)[];
  laps?: number[];
  lap_times?: number[];
  compounds?: string[];
  weather?: string;
  turn_number?: number;
  corner_nickname?: string;
  sector_boundaries_m?: number[];
  metrics?: any;
  [key: string]: unknown;
}

export interface PlotlySpec {
  data?: any[];
  layout?: Record<string, any>;
  config?: Record<string, any>;
  viz_type?: string;
  chart_type?: string;
  title?: string;
  figure?: any;
  minimap?: any;
  kpi_card?: KpiCardData;
  data_table?: DataTableData;
  web_intelligence_card?: WebIntelligenceCardData;
  metadata?: ChartMetadata;
}

export interface SSEStatusEvent {
  step: string;
  detail: string;
}
