(() => {
  const input = document.getElementById("id_photo");
  const editor = document.getElementById("student-photo-editor");
  const canvas = document.getElementById("student-photo-canvas");
  const zoomInput = document.getElementById("student-photo-zoom");
  const status = document.getElementById("student-photo-editor-status");
  const applyButton = document.getElementById("student-photo-apply");
  const cancelButton = document.getElementById("student-photo-cancel");
  const compressedNote = document.getElementById("student-photo-compressed-note");
  if (!input || !editor || !canvas || !zoomInput) return;

  const form = input.closest("form");
  const saveButton = form.querySelector('button[type="submit"]');
  const context = canvas.getContext("2d", { alpha: false });
  const targetBytes = 1.5 * 1024 * 1024;
  let sourceImage = null;
  let sourceUrl = null;
  let resultUrl = null;
  let crop = null;
  let dragPoint = null;
  let readyToSubmit = false;

  saveButton.disabled = true;

  const formatSize = (bytes) => `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  const clampCrop = () => {
    const maxX = sourceImage.naturalWidth - crop.side;
    const maxY = sourceImage.naturalHeight - crop.side;
    crop.x = Math.max(0, Math.min(maxX, crop.x));
    crop.y = Math.max(0, Math.min(maxY, crop.y));
  };

  function drawCrop() {
    if (!sourceImage || !crop) return;
    clampCrop();
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(
      sourceImage,
      crop.x,
      crop.y,
      crop.side,
      crop.side,
      0,
      0,
      canvas.width,
      canvas.height,
    );
  }

  function beginEditing(file) {
    readyToSubmit = false;
    saveButton.disabled = true;
    compressedNote.hidden = true;
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrl = null;
    sourceUrl = URL.createObjectURL(file);
    sourceImage = new Image();
    sourceImage.onload = () => {
      const shortestSide = Math.min(sourceImage.naturalWidth, sourceImage.naturalHeight);
      crop = {
        side: shortestSide,
        x: (sourceImage.naturalWidth - shortestSide) / 2,
        y: (sourceImage.naturalHeight - shortestSide) / 2,
      };
      zoomInput.value = "1";
      editor.hidden = false;
      status.textContent = `Foto asli ${formatSize(file.size)}. Geser dan crop sebelum disimpan.`;
      drawCrop();
    };
    sourceImage.onerror = () => {
      editor.hidden = false;
      status.textContent = "Foto ini tidak bisa dibuka. Pilih file JPG, PNG, atau WebP.";
    };
    sourceImage.src = sourceUrl;
  }

  function resizeCrop() {
    const zoom = Number(zoomInput.value);
    const centerX = crop.x + crop.side / 2;
    const centerY = crop.y + crop.side / 2;
    crop.side = Math.min(sourceImage.naturalWidth, sourceImage.naturalHeight) / zoom;
    crop.x = centerX - crop.side / 2;
    crop.y = centerY - crop.side / 2;
    drawCrop();
  }

  function canvasToBlob(targetCanvas, quality) {
    return new Promise((resolve) => targetCanvas.toBlob(resolve, "image/jpeg", quality));
  }

  async function makeCompressedPhoto() {
    const output = document.createElement("canvas");
    let dimension = Math.min(960, Math.round(crop.side));
    const qualities = [0.88, 0.8, 0.72, 0.64, 0.56];

    while (dimension >= 320) {
      output.width = dimension;
      output.height = dimension;
      output.getContext("2d", { alpha: false }).drawImage(
        sourceImage,
        crop.x,
        crop.y,
        crop.side,
        crop.side,
        0,
        0,
        dimension,
        dimension,
      );
      for (const quality of qualities) {
        const blob = await canvasToBlob(output, quality);
        if (blob && blob.size <= targetBytes) return blob;
      }
      dimension = Math.floor(dimension * 0.8);
    }
    return null;
  }

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (!file) return;
    beginEditing(file);
  });

  zoomInput.addEventListener("input", resizeCrop);
  canvas.addEventListener("pointerdown", (event) => {
    if (!sourceImage) return;
    dragPoint = { x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragPoint || !crop) return;
    const bounds = canvas.getBoundingClientRect();
    const scale = crop.side / bounds.width;
    crop.x -= (event.clientX - dragPoint.x) * scale;
    crop.y -= (event.clientY - dragPoint.y) * scale;
    dragPoint = { x: event.clientX, y: event.clientY };
    drawCrop();
  });
  canvas.addEventListener("pointerup", () => { dragPoint = null; });
  canvas.addEventListener("pointercancel", () => { dragPoint = null; });

  applyButton.addEventListener("click", async () => {
    if (!sourceImage || !crop) return;
    applyButton.disabled = true;
    cancelButton.disabled = true;
    status.textContent = "Sedang crop dan mengecilkan ukuran foto…";
    try {
      const blob = await makeCompressedPhoto();
      if (!blob) throw new Error("Ukuran foto belum bisa diperkecil. Coba crop bagian yang lebih dekat.");
      const outputFile = new File(
        [blob],
        `foto-profil-${Date.now()}.jpg`,
        { type: "image/jpeg", lastModified: Date.now() },
      );
      const transfer = new DataTransfer();
      transfer.items.add(outputFile);
      input.files = transfer.files;
      readyToSubmit = true;
      saveButton.disabled = false;
      editor.hidden = true;
      resultUrl = URL.createObjectURL(outputFile);
      compressedNote.textContent = `Siap diunggah: ${formatSize(outputFile.size)} (hasil crop otomatis dikompres).`;
      compressedNote.hidden = false;
    } catch (error) {
      status.textContent = error.message || "Foto gagal diproses. Coba file lain.";
    } finally {
      applyButton.disabled = false;
      cancelButton.disabled = false;
    }
  });

  cancelButton.addEventListener("click", () => {
    input.value = "";
    readyToSubmit = false;
    saveButton.disabled = true;
    editor.hidden = true;
    compressedNote.hidden = true;
    sourceImage = null;
    crop = null;
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    sourceUrl = null;
    resultUrl = null;
  });

  form.addEventListener("submit", (event) => {
    if (!readyToSubmit) {
      event.preventDefault();
      status.textContent = "Pilih foto, atur crop, lalu gunakan hasil crop sebelum menyimpan.";
      editor.hidden = false;
    }
  });
})();
