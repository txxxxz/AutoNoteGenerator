export const debug = {
  info: (...args: unknown[]) => console.info('%c[StudyCompanion][信息]', 'color: #3f60ff;', ...args),
  warn: (...args: unknown[]) => console.warn('%c[StudyCompanion][警告]', 'color: #d67b00;', ...args),
  error: (...args: unknown[]) => console.error('%c[StudyCompanion][错误]', 'color: #d64550;', ...args)
};
