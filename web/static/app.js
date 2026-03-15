async function loadEvents() {
  const res = await fetch('/api/events');
  const payload = await res.json();
  const events = payload.events || [];
  const el = document.getElementById('events');
  const badge = document.getElementById('stateBadge');
  badge.textContent = payload.state ? `(${payload.state})` : '';
  el.innerHTML = events.length
    ? events.slice(-20).reverse().map(e => {
        const ts = e.ts ? new Date(e.ts * 1000).toLocaleString() : 'без времени';
        const extra = e.s3_key ? ` · S3: ${e.s3_key}` : '';
        return `<div><strong>${e.type}</strong> — ${ts}${extra}</div>`;
      }).join('')
    : '<div>Нет событий</div>';
}

async function loadLog() {
  const res = await fetch('/api/log?lines=120');
  const payload = await res.json();
  document.getElementById('watchlog').textContent = payload.log || '';
}

async function loadRecordings() {
  const res = await fetch('/api/recordings');
  const files = await res.json();
  const el = document.getElementById('recordings');
  el.innerHTML = files.length
    ? files.map(f => `
      <div>
        <video controls preload="metadata" width="100%" src="${f.path}"></video>
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

async function loadCameraStatus() {
  const res = await fetch('/api/camera/status');
  const data = await res.json();
  const status = document.getElementById('cameraStatus');
  const btn = document.getElementById('cameraRecordBtn');
  if (data.recording) {
    btn.textContent = 'Остановить запись';
    btn.classList.add('recording-live');
    status.textContent = `Идёт запись с ${new Date(data.started_at).toLocaleTimeString()} · кадров: ${data.frames}`;
  } else {
    btn.textContent = 'Начать запись';
    btn.classList.remove('recording-live');
    status.textContent = 'Поток доступен по локальной сети';
  }
}

async function toggleCameraRecording() {
  const btn = document.getElementById('cameraRecordBtn');
  const result = document.getElementById('cameraResult');
  const shouldStop = btn.classList.contains('recording-live');
  btn.disabled = true;
  result.textContent = shouldStop ? 'Остановка записи и сборка файла...' : 'Старт записи...';
  try {
    const res = await fetch(shouldStop ? '/api/camera/record/stop' : '/api/camera/record/start', {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Ошибка камеры');
    if (shouldStop) {
      const audioText = data.with_audio ? 'со звуком' : 'без звука';
      const s3Text = data.s3_key ? ` · S3: ${data.s3_key}` : '';
      result.innerHTML = `Готово: <a href="${data.path}" target="_blank">${data.name}</a> (${audioText})${s3Text}`;
      loadRecordings();
    } else {
      result.textContent = 'Запись запущена.';
    }
  } catch (e) {
    result.textContent = 'Ошибка: ' + e.message;
  } finally {
    btn.disabled = false;
    loadCameraStatus();
    loadEvents();
  }
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

document.getElementById('cameraRecordBtn').addEventListener('click', toggleCameraRecording);
document.getElementById('cameraRefreshBtn').addEventListener('click', loadCameraStatus);

let mediaRecorder;
let audioChunks;
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

document.getElementById('cameraStream').addEventListener('error', () => {
  document.getElementById('cameraStatus').textContent = 'Поток камеры недоступен';
});

loadEvents();
loadLog();
loadRecordings();
loadSnapshots();
loadCameraStatus();
setInterval(loadEvents, 5000);
setInterval(loadLog, 5000);
setInterval(loadCameraStatus, 3000);
