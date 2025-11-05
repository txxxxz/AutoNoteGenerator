import axios from 'axios';
import { debug } from './debug';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 60000
});

client.interceptors.request.use((config) => {
  debug.info('发起 API 请求', config.method?.toUpperCase(), config.url, config.params ?? '', config.data ?? '');
  return config;
});

client.interceptors.response.use(
  (response) => {
    debug.info('API 响应成功', response.config.url, response.status, response.data);
    return response;
  },
  (error) => {
    if (error.response) {
      debug.error('API 响应失败', error.config?.url, error.response.status, error.response.data);
    } else {
      debug.error('API 请求异常', error.message);
    }
    return Promise.reject(error);
  }
);

export default client;
