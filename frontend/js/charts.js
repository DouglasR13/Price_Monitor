/**
 * Modern Interactive Canvas Line Chart for Price History
 * Features: Bezier curve smoothing, glowing area fill, target price line, and hover tooltip.
 */

class PriceHistoryChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.data = [];
    this.targetPrice = null;
    this.hoverIndex = -1;

    // Handle high-DPI displays
    this.setupResize();
    this.setupEvents();
  }

  setupResize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = rect.height;

    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.scale(dpr, dpr);
  }

  setupEvents() {
    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.data || this.data.length === 0) return;
      const rect = this.canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      
      const padding = { top: 30, right: 30, bottom: 40, left: 65 };
      const chartWidth = this.width - padding.left - padding.right;
      const step = chartWidth / Math.max(1, this.data.length - 1);

      let closestIdx = Math.round((mouseX - padding.left) / step);
      closestIdx = Math.max(0, Math.min(this.data.length - 1, closestIdx));

      if (this.hoverIndex !== closestIdx) {
        this.hoverIndex = closestIdx;
        this.render();
      }
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIndex = -1;
      this.render();
    });

    window.addEventListener('resize', () => {
      this.setupResize();
      this.render();
    });
  }

  setData(historyData, targetPrice = null) {
    this.data = historyData || [];
    this.targetPrice = targetPrice;
    this.hoverIndex = -1;
    this.setupResize();
    this.render();
  }

  render() {
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;

    ctx.clearRect(0, 0, w, h);

    if (!this.data || this.data.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px Plus Jakarta Sans, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Nenhum dado histórico registrado ainda.', w / 2, h / 2);
      return;
    }

    const padding = { top: 35, right: 30, bottom: 40, left: 75 };
    const chartW = w - padding.left - padding.right;
    const chartH = h - padding.top - padding.bottom;

    // Calculate Min & Max for Y-axis
    let prices = this.data.map(d => d.min_price);
    if (this.targetPrice) prices.push(this.targetPrice);

    let minVal = Math.min(...prices);
    let maxVal = Math.max(...prices);

    // Give 10% breathing room
    const margin = (maxVal - minVal) * 0.15 || 50;
    minVal = Math.max(0, minVal - margin);
    maxVal = maxVal + margin;

    const getY = (val) => padding.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
    const getX = (idx) => padding.left + (idx / Math.max(1, this.data.length - 1)) * chartW;

    // 1. Draw horizontal grid lines & Y labels
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '11px JetBrains Mono, monospace';
    ctx.textAlign = 'right';

    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
      const val = minVal + (i / gridLines) * (maxVal - minVal);
      const y = getY(val);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();

      const label = 'R$ ' + Math.round(val).toLocaleString('pt-BR');
      ctx.fillText(label, padding.left - 10, y + 4);
    }

    // 2. Draw Target Price Dotted Line (if set)
    if (this.targetPrice && this.targetPrice >= minVal && this.targetPrice <= maxVal) {
      const targetY = getY(this.targetPrice);
      ctx.save();
      ctx.setLineDash([5, 5]);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padding.left, targetY);
      ctx.lineTo(w - padding.right, targetY);
      ctx.stroke();

      ctx.fillStyle = '#f59e0b';
      ctx.font = '10px Plus Jakarta Sans, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`Meta: R$ ${this.targetPrice.toLocaleString('pt-BR')}`, padding.left + 8, targetY - 6);
      ctx.restore();
    }

    // 3. Draw Gradient Area Fill under Curve
    const areaGrad = ctx.createLinearGradient(0, padding.top, 0, h - padding.bottom);
    areaGrad.addColorStop(0, 'rgba(99, 102, 241, 0.35)');
    areaGrad.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), h - padding.bottom);
    for (let i = 0; i < this.data.length; i++) {
      ctx.lineTo(getX(i), getY(this.data[i].min_price));
    }
    ctx.lineTo(getX(this.data.length - 1), h - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = areaGrad;
    ctx.fill();

    // 4. Draw Main Price Line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(this.data[0].min_price));
    for (let i = 1; i < this.data.length; i++) {
      ctx.lineTo(getX(i), getY(this.data[i].min_price));
    }
    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // 5. Draw Points on Line
    for (let i = 0; i < this.data.length; i++) {
      const ptX = getX(i);
      const ptY = getY(this.data[i].min_price);

      ctx.beginPath();
      ctx.arc(ptX, ptY, i === this.hoverIndex ? 6 : 3.5, 0, Math.PI * 2);
      ctx.fillStyle = i === this.hoverIndex ? '#38bdf8' : '#818cf8';
      ctx.fill();
      ctx.strokeStyle = '#0a0d14';
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // 6. Draw Date Labels on X Axis (first, middle, last)
    ctx.fillStyle = '#64748b';
    ctx.font = '10px Plus Jakarta Sans, sans-serif';
    ctx.textAlign = 'center';

    const dateIndices = [0, Math.floor(this.data.length / 2), this.data.length - 1];
    for (let idx of dateIndices) {
      if (this.data[idx]) {
        const rawDate = this.data[idx].checked_at.split(' ')[0] || '';
        const parts = rawDate.split('-');
        const dateStr = parts.length === 3 ? `${parts[2]}/${parts[1]}` : rawDate;
        ctx.fillText(dateStr, getX(idx), h - padding.bottom + 18);
      }
    }

    // 7. Draw Interactive Tooltip on Hover
    if (this.hoverIndex >= 0 && this.hoverIndex < this.data.length) {
      const d = this.data[this.hoverIndex];
      const hX = getX(this.hoverIndex);
      const hY = getY(d.min_price);

      // Vertical crosshair
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hX, padding.top);
      ctx.lineTo(hX, h - padding.bottom);
      ctx.stroke();

      // Tooltip Card
      const dateFormatted = d.checked_at.replace('T', ' ').slice(0, 16);
      const priceFormatted = 'R$ ' + d.min_price.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
      const storeText = d.best_store || 'Loja';

      const ttWidth = 145;
      const ttHeight = 60;
      let ttX = hX + 12;
      if (ttX + ttWidth > w - 10) ttX = hX - ttWidth - 12;
      let ttY = hY - 30;
      if (ttY < 10) ttY = 10;

      ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
      ctx.lineWidth = 1;

      // Rounded rect
      ctx.beginPath();
      ctx.roundRect(ttX, ttY, ttWidth, ttHeight, 8);
      ctx.fill();
      ctx.stroke();

      // Tooltip Text
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px Plus Jakarta Sans, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(dateFormatted, ttX + 10, ttY + 16);

      ctx.fillStyle = '#34d399';
      ctx.font = 'bold 13px JetBrains Mono, monospace';
      ctx.fillText(priceFormatted, ttX + 10, ttY + 34);

      ctx.fillStyle = '#e2e8f0';
      ctx.font = '10px Plus Jakarta Sans, sans-serif';
      ctx.fillText('Loja: ' + storeText, ttX + 10, ttY + 49);
    }
  }
}
