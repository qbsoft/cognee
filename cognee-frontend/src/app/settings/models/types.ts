export interface ConfigField {
  key: string;
  label: string;
  label_en: string;
  type: string;
  required: boolean;
  placeholder: string;
  help_text: string;
  help_text_en: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  capabilities: string[];
  max_tokens: number;
  is_default: boolean;
}

export interface Provider {
  id: string;
  name: string;
  name_en: string;
  category: string;
  icon: string;
  default_base_url: string;
  is_openai_compatible: boolean;
  auth_type: string;
  capabilities: string[];
  notes: string;
  notes_en: string;
  is_configured: boolean;
  is_enabled: boolean;
  api_key_preview: string;
  base_url: string;
  models: ModelInfo[];
  config_fields: ConfigField[];
}

export interface ProviderCategory {
  label: string;
  label_en: string;
  providers: Provider[];
}

export interface ProviderCategories {
  [key: string]: ProviderCategory;
}

export interface DefaultModelSelection {
  provider_id: string;
  model_id: string;
}

export interface UserDefaults {
  [taskType: string]: DefaultModelSelection;
}

export interface ConnectionTestResult {
  success: boolean;
  latency_ms: number;
  error: string;
  models_discovered: string[] | null;
}
