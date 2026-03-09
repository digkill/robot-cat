async function loadEvents() {
  const res = await fetch('/api/events');
  const events = await res.json();
  const el = document.getElementById('events');
  el.innerHTML = events.length
    ? events.slice(-20).reverse().map(e => {
        const d = new Date(e.ts * 1000).toLocaleString();
        return `<div><strong>${e.type}</strong> — ${d}</div>`;
      }).join('')
    : '<div>Нет событий</div>';
}

async function loadRecordings() {
  const res = await fetch('/api/recordings');
  const files = await res.json();
  const el = document.getElementById('recordings');
  el.innerHTML = files.length
    ? files.map(f => `
      <div>
        <video controls width="100%" src="${f.path}"></video>
        <a href="${f.path}" download>${f.name}</a>
      </div>
    `).join('')
    : '<div>Нет записей</div>';
}

async function loadSnapshots() {
  const res = await fetch('/api/snapshots');
  const files = await res.json();
  const el = document.getElementById('snapshots');
  el.innerHTML = files.length
    ? files.map(f => `
      <div>
        <img src="${f.path}" alt="${f.name}" loading="lazy" />
        <a href="${f.path}" download>${f.name}</a>
      </div>
    `).join('')
    : '<div>Нет снимков</div>';
}

async function sendToAssistant() {
  const input = document.getElementById('assistantInput');
  const text = input.value.trim();
  if (!text) return;
  const replyEl = document.getElementById('assistantReply');
  replyEl.textContent = '...';
  try {
    const res = await fetch('/api/assistant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    replyEl.textContent = data.reply || data.error || 'Нет ответа';
  } catch (e) {
    replyEl.textContent = 'Ошибка: ' + e.message;
  }
  input.value = '';
}

document.getElementById('assistantInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendToAssistant();
});

// Запись с микрофона
let mediaRecorder, audioChunks;
document.getElementById('recordBtn').addEventListener('click', async () => {
  const btn = document.getElementById('recordBtn');
  const status = document.getElementById('recordStatus');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = e => e.data.size && audioChunks.push(e.data);
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      const fd = new FormData();
      fd.append('audio', blob, 'recording.webm');
      status.textContent = 'Отправка...';
      btn.textContent = '🎙️ Записать голос';
      try {
        const res = await fetch('/api/audio/upload', { method: 'POST', body: fd });
        const data = await res.json();
        status.textContent = data.path ? 'Сохранено: ' + data.name : (data.error || 'Ошибка');
        if (data.path) loadRecordings();
      } catch (e) {
        status.textContent = 'Ошибка: ' + e.message;
      }
      btn.classList.remove('recording');
    };
    mediaRecorder.start();
    btn.classList.add('recording');
    btn.textContent = '⏹ Остановить';
    status.textContent = 'Запись...';
  } catch (e) {
    status.textContent = 'Ошибка: ' + e.message;
  }
});

loadEvents();
loadRecordings();
loadSnapshots();
setInterval(loadEvents, 5000);
