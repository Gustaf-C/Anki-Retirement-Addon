function setup(options) {

  const store = options.auxData();
  const retireOptions = document.querySelectorAll('.retireOption');
  const deleteCheckbox = document.getElementById("delete");
  const suspendCheckbox = document.getElementById("suspend");
  const tagCheckbox = document.getElementById("tag");
  const moveCheckbox = document.getElementById("move");
  const retireInterval = document.getElementById("interval");

  // update html when state changes
  store.subscribe((data) => {
    data.retirementOptions = data.retirementOptions ?? {};
    data.retirementOptions.retire = data.retirementOptions.retire ?? false;
    data.retirementOptions.delete = data.retirementOptions.delete ?? false;
    data.retirementOptions.suspend = data.retirementOptions.suspend ?? false;
    data.retirementOptions.tag = data.retirementOptions.tag ?? false;
    data.retirementOptions.move = data.retirementOptions.move ?? false;
    data.retirementOptions.retireInterval = data.retirementOptions.retireInterval ?? 0;

    deleteCheckbox.checked = data.retirementOptions.delete;
    suspendCheckbox.checked = data.retirementOptions.suspend;
    tagCheckbox.checked = data.retirementOptions.tag;
    moveCheckbox.checked = data.retirementOptions.move;

    if (data.retirementOptions.retireInterval < 0){
      data.retirementOptions.retireInterval === 0;
      retireInterval.value = data.retirementOptions.retireInterval;
    } else {retireInterval.value = data.retirementOptions.retireInterval};

    if ((data.retirementOptions.delete === true ||
      data.retirementOptions.suspend === true ||
      data.retirementOptions.tag === true ||
      data.retirementOptions.move === true) &&
      data.retirementOptions.retireInterval > 0) {
      data.retirementOptions.retire = true;
    } else {
      data.retirementOptions.retire = false;
    }

    // and show current data for debugging
    document.getElementById("debug").innerText = JSON.stringify(data, null, 4);
  });

  for (const retireOption of retireOptions) {
    retireOption.addEventListener('change', (_) => {
      store.update((data) => {
        return { ...data, retirementOptions: { ...data.retirementOptions, retire: data.retirementOptions.retire } };
      })
    });
  }

  deleteCheckbox.addEventListener("change", (_) =>
  store.update((data) => {
    return { ...data, retirementOptions: { ...data.retirementOptions, delete: deleteCheckbox.checked } };
  })
  );

  suspendCheckbox.addEventListener("change", (_) =>
  store.update((data) => {
    return { ...data, retirementOptions: { ...data.retirementOptions, suspend: suspendCheckbox.checked } };
  })
  );
  
  tagCheckbox.addEventListener("change", (_) =>
  store.update((data) => {
    return { ...data, retirementOptions: { ...data.retirementOptions, tag: tagCheckbox.checked } };
  })
  );

  moveCheckbox.addEventListener("change", (_) =>
  store.update((data) => {
    return { ...data, retirementOptions: { ...data.retirementOptions, move: moveCheckbox.checked } };
  })
  );

  retireInterval.addEventListener("change", (_) => {
    let number = 0;
    try {
      number = parseInt(retireInterval.value, 10);
    } catch (err) {}

    store.update((data) => {
      return { ...data, retirementOptions: { ...data.retirementOptions, retireInterval: number } };
    });
  });
}


function handleDeleteCheckbox() {
  var deleteCheckbox = document.getElementById("delete");
  var suspendCheckbox = document.getElementById("suspend");
  var tagCheckbox = document.getElementById("tag");
  var moveCheckbox = document.getElementById("move");

  if (deleteCheckbox.checked) {
      suspendCheckbox.disabled = true;
      tagCheckbox.disabled = true;
      moveCheckbox.disabled = true;
  } else {
      suspendCheckbox.disabled = false;
      tagCheckbox.disabled = false;
      moveCheckbox.disabled = false;
  }
}

$deckOptions.then((options) => {
options.addHtmlAddon(HTML_CONTENT, () => setup(options));
});