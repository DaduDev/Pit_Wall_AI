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

export interface EngineeringTrace {
  data_domain: 'historical' | 'telemetry' | 'mixed';
  query?: string;
  execution_time_ms?: number;
  row_count?: number;
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
  interpolated_points?: number;
  confidence: number;
  notes?: string;
}

export interface PlotlySpec {
  data: any[];
  layout: Record<string, any>;
  config?: Record<string, any>;
  chart_type?: string;
  metadata?: {
    event_name?: string;
    year?: number;
    session_type?: string;
    drivers?: string[];
    driver_numbers?: (number | string)[];
    laps?: number[];
    lap_times?: number[];
    compounds?: string[];
    weather?: string;
    turn_number?: number;
    corner_nickname?: string;
    sector_boundaries_m?: number[];
    metrics?: any;
  };
}

export interface SSEStatusEvent {
  step: string;
  detail: string;
}
