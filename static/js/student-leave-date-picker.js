(() => {
  document.querySelectorAll('.student-leave-page input[name="date_from"], .student-leave-page input[name="date_to"]').forEach((textInput) => {
    const control = document.createElement("span");
    control.className = "student-date-control";
    textInput.parentNode.insertBefore(control, textInput);
    control.appendChild(textInput);

    const calendarButton = document.createElement("button");
    calendarButton.type = "button";
    calendarButton.className = "student-date-picker-button";
    calendarButton.setAttribute("aria-label", `Pilih ${textInput.labels[0]?.textContent || "tanggal"} dari kalender`);
    calendarButton.innerHTML = '<span class="msym" aria-hidden="true">calendar_month</span>';

    const datePicker = document.createElement("input");
    datePicker.type = "date";
    datePicker.lang = "id";
    datePicker.tabIndex = -1;
    datePicker.setAttribute("aria-hidden", "true");
    datePicker.className = "student-date-native-picker";
    control.append(calendarButton, datePicker);

    const syncPickerFromText = () => {
      const match = textInput.value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
      if (!match) {
        datePicker.value = "";
        return;
      }
      const [, dayText, monthText, yearText] = match;
      const day = Number(dayText);
      const month = Number(monthText);
      const year = Number(yearText);
      const candidate = new Date(year, month - 1, day);
      datePicker.value = candidate.getFullYear() === year
        && candidate.getMonth() === month - 1
        && candidate.getDate() === day
        ? `${yearText}-${monthText}-${dayText}`
        : "";
    };

    textInput.addEventListener("input", syncPickerFromText);
    calendarButton.addEventListener("click", () => {
      syncPickerFromText();
      try {
        if (typeof datePicker.showPicker === "function") datePicker.showPicker();
        else {
          datePicker.focus();
          datePicker.click();
        }
      } catch {
        datePicker.focus();
        datePicker.click();
      }
    });
    datePicker.addEventListener("change", () => {
      if (!datePicker.value) return;
      const [year, month, day] = datePicker.value.split("-");
      textInput.value = `${day}/${month}/${year}`;
      textInput.dispatchEvent(new Event("input", { bubbles: true }));
      textInput.dispatchEvent(new Event("change", { bubbles: true }));
    });
    syncPickerFromText();
  });
})();
