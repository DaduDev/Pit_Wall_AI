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
    drivers?: string[];
    turn_number?: number;
    corner_nickname?: string;
  };
  interpolated_points?: number;
  confidence: number;
  notes?: string;
}

export interface PlotlySpec {
  data: any[];
  layout: Record<string, any>;
  config?: Record<string, any>;
}

export interface SSEStatusEvent {
  step: string;
  detail: string;
}
