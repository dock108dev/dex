'use strict';
/* Shared Hunter/Discovery auction display. Missing dates never become epoch zero. */
window.DexAuctionTime = (value, now = Date.now()) => {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value)) return 'Auction · end time unknown';
  const [year,month,day,hour,minute,second] = value.slice(0,19).split(/[-T:]/).map(Number);
  const days = [31,year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28,31,30,31,30,31,31,30,31,30,31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month-1] || hour > 23 || minute > 59 || second > 59) return 'Auction · end time unknown';
  const end = new Date(value), left = end.getTime() - now;
  if (!Number.isFinite(left)) return 'Auction · end time unknown';
  const date = end.toLocaleString();
  return left <= 0 ? `Auction ended · ${date}` : `Auction · ${Math.floor(left / 3600000)}h ${Math.floor(left % 3600000 / 60000)}m remaining · ends ${date}`;
};
