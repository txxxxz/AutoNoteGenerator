import { FormEvent, useEffect, useMemo, useState } from 'react';

import { fetchLlmSettings, updateLlmSettings } from '../api/routes';
import { LlmProvider, LlmSettingsPayload, LlmSettingsResponse } from '../api/types';
import '../styles/api-settings.css';

type ApiSettingsForm = {
  provider: LlmProvider;
  base_url: string;
  llm_model: string;
  embedding_model: string;
  api_key: string;
};

const providerOptions: Array<{ value: LlmProvider; label: string }> = [
  { value: 'google', label: 'Google Gemini' },
  { value: 'openai', label: 'OpenAI / 兼容' }
];

const llmPresets: Record<LlmProvider, string[]> = {
  google: ['gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-1.5-flash-8b'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-3.5-turbo']
};

const embeddingPresets: Record<LlmProvider, string[]> = {
  google: ['models/embedding-001', 'text-multilingual-embedding-002'],
  openai: ['text-embedding-3-large', 'text-embedding-3-small']
};

type ApiKeyMode = 'unchanged' | 'set' | 'clear';

const ApiSettingsPanel = () => {
  const [form, setForm] = useState<ApiSettingsForm>({
    provider: 'google',
    base_url: '',
    llm_model: '',
    embedding_model: '',
    api_key: ''
  });
  const [apiKeyHint, setApiKeyHint] = useState<string | null>(null);
  const [apiKeyMode, setApiKeyMode] = useState<ApiKeyMode>('unchanged');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const settings = await fetchLlmSettings();
        if (!mounted) return;
        applyResponse(settings);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : '无法加载 API 设置');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const applyResponse = (settings: LlmSettingsResponse) => {
    setForm((prev) => ({
      ...prev,
      provider: settings.provider,
      base_url: settings.base_url ?? '',
      llm_model: settings.llm_model ?? '',
      embedding_model: settings.embedding_model ?? '',
      api_key: ''
    }));
    setApiKeyHint(settings.api_key_preview ?? (settings.api_key_present ? '已保存' : null));
    setApiKeyMode('unchanged');
    setMessage(null);
    setError(null);
  };

  const handleInputChange = (field: keyof ApiSettingsForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === 'api_key') {
      setApiKeyMode(value ? 'set' : 'unchanged');
    }
  };

  const handleProviderChange = (provider: LlmProvider) => {
    setForm((prev) => ({ ...prev, provider }));
  };

  const handleClearKey = () => {
    setApiKeyMode('clear');
    setForm((prev) => ({ ...prev, api_key: '' }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const payload: LlmSettingsPayload = {
        provider: form.provider,
        base_url: form.base_url.trim(),
        llm_model: form.llm_model.trim(),
        embedding_model: form.embedding_model.trim()
      };
      if (apiKeyMode === 'set' && form.api_key.trim()) {
        payload.api_key = form.api_key.trim();
      } else if (apiKeyMode === 'clear') {
        payload.api_key = '';
      }
      const response = await updateLlmSettings(payload);
      applyResponse(response);
      setMessage('已保存 API 设置并立即生效。');
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const currentLlmOptions = useMemo(() => llmPresets[form.provider], [form.provider]);
  const currentEmbeddingOptions = useMemo(() => embeddingPresets[form.provider], [form.provider]);

  if (loading) {
    return <div className="api-settings__placeholder">加载 API 设置中…</div>;
  }

  return (
    <section className="api-settings">
      <header>
        <h2>API 设置</h2>
        <p>配置推理接口的密钥、模型与 Base URL，确保能够调用正确的 LLM。</p>
      </header>
      <form onSubmit={handleSubmit} className="api-settings__form">
        <div className="api-settings__grid">
          <label>
            <span>服务提供方</span>
            <select
              value={form.provider}
              onChange={(event) => handleProviderChange(event.target.value as LlmProvider)}
            >
              {providerOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>基础 URL（OpenAI 兼容时使用）</span>
            <input
              type="text"
              placeholder="https://api.openai.com/v1"
              value={form.base_url}
              onChange={(event) => handleInputChange('base_url', event.target.value)}
            />
            <small>官方 OpenAI 可以留空，第三方兼容服务请填写完整 URL。</small>
          </label>
          <label>
            <span>LLM 模型</span>
            <input
              type="text"
              list="llm-models"
              placeholder={form.provider === 'google' ? 'gemini-1.5-flash-latest' : 'gpt-4o-mini'}
              value={form.llm_model}
              onChange={(event) => handleInputChange('llm_model', event.target.value)}
            />
            <datalist id="llm-models">
              {currentLlmOptions.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
          </label>
          <label>
            <span>Embedding 模型</span>
            <input
              type="text"
              list="embedding-models"
              placeholder={form.provider === 'google' ? 'models/embedding-001' : 'text-embedding-3-large'}
              value={form.embedding_model}
              onChange={(event) => handleInputChange('embedding_model', event.target.value)}
            />
            <datalist id="embedding-models">
              {currentEmbeddingOptions.map((model) => (
                <option key={model} value={model} />
              ))}
            </datalist>
          </label>
          <label>
            <span>API Key</span>
            <input
              type="password"
              placeholder="请输入新的 API Key"
              value={form.api_key}
              onChange={(event) => handleInputChange('api_key', event.target.value)}
            />
            {apiKeyHint ? <small>已保存：{apiKeyHint}</small> : <small>保存后会安全存储在本地服务器。</small>}
            <button
              type="button"
              className="api-settings__clear-btn"
              onClick={handleClearKey}
              disabled={apiKeyMode === 'clear'}
            >
              清空已保存 Key
            </button>
          </label>
        </div>
        {message && <p className="api-settings__success" role="status">{message}</p>}
        {error && <p className="api-settings__error" role="alert">{error}</p>}
        <div className="api-settings__actions">
          <button type="submit" disabled={saving}>
            {saving ? '保存中…' : '保存设置'}
          </button>
        </div>
      </form>
    </section>
  );
};

export default ApiSettingsPanel;
