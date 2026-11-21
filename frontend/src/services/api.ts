import axios from 'axios';
import type { Ticket, WardScore, SystemStats } from '../types';

const axiosInstance = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add response interceptor for error handling
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    throw error;
  }
);

// Unified API object
export const api = {
  createReport: async (formData: FormData) => {
    const response = await axiosInstance.post('/reports', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getTickets: async (params?: {
    status?: string;
    ward_id?: string;
    officer_id?: string;
    category?: string;
    escalated_only?: boolean;
  }): Promise<Ticket[]> => {
    // Strip empty-string params so FastAPI doesn't reject them
    const clean: Record<string, any> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== '' && v !== undefined && v !== null) clean[k] = v;
      });
    }
    const response = await axiosInstance.get<Ticket[]>('/tickets', { params: clean });
    return response.data;
  },

  // Backend returns flat ticket object with events[] and contractor_info embedded
  getTicketDetail: async (id: string): Promise<Ticket> => {
    const response = await axiosInstance.get(`/tickets/${id}`);
    return response.data;
  },

  submitResolution: async (id: string, formData: FormData) => {
    const response = await axiosInstance.post(`/tickets/${id}/resolution`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  submitFeedback: async (id: string, verified: boolean) => {
    const formData = new FormData();
    formData.append('verified', verified.toString());
    const response = await axiosInstance.post(`/tickets/${id}/feedback`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  requestClockStop: async (id: string, reason: string, officer_id: number) => {
    const formData = new FormData();
    formData.append('reason', reason);
    formData.append('officer_id', officer_id.toString());
    const response = await axiosInstance.post(`/tickets/${id}/clock-stop`, formData);
    return response.data;
  },

  getWardScores: async (): Promise<WardScore[]> => {
    const response = await axiosInstance.get('/wards/scores');
    return response.data.wards || [];
  },

  getStats: async (): Promise<SystemStats> => {
    const response = await axiosInstance.get<SystemStats>('/stats');
    return response.data;
  },

  downloadEvidence: async (id: string) => {
    const url = `${axiosInstance.defaults.baseURL}/tickets/${id}/evidence.pdf`;
    window.open(url, '_blank');
  },

  fastForward: async (hours: number) => {
    const response = await axiosInstance.post(`/admin/fast-forward?hours=${hours}`);
    return response.data;
  },
};

// ticketAPI alias used by TicketCard (submitResolution + downloadEvidence returning blob)
export const ticketAPI = {
  submitResolution: async (id: number, formData: FormData) => {
    const response = await axiosInstance.post(`/tickets/${id}/resolution`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  downloadEvidence: async (id: number): Promise<Blob> => {
    const response = await axiosInstance.get(`/tickets/${id}/evidence.pdf`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export default axiosInstance;
