const optionDefinitions = {
		remember: {
			type: 'boolean',
			desc: 'Remember editor value',
			default: true
		},
		indentType: {
			type: 'dropdown',
			desc: 'Indent type',
			values: [
				{
					val: '2',
					name: '2 Spaces'
				},
				{
					val: '4',
					name: '4 Spaces'
				},
				{
					val: '8',
					name: '8 Spaces'
				},
				{
					val: 'tab',
					name: 'Tab character'
				}
			],
			default: '4'
		},
		wordWrap: {
			type: 'boolean',
			desc: 'Word wrap',
			default: true
		},
		autoComplete: {
			type: 'boolean',
			desc: 'Autocomplete',
			default: true
		},
		showGutter: {
			type: 'boolean',
			desc: 'Show gutter',
			default: true
		},
		scrollPastEnd: {
			type: 'boolean',
			desc: 'Scroll past end of code',
			default: false
		},
		popupColorScheme: {
			type: 'dropdown',
			desc: 'Popup Theme',
			values: [
				{
					val: 'system',
					name: 'System'
				},
				{
					val: 'light',
					name: 'Light'
				},
				{
					val: 'dark',
					name: 'Dark'
				}
			],
			default: 'system',
			show: !chrome.devtools
		}
	},
	optionDefaults = Object.fromEntries(
		Object.entries(optionDefinitions).map(([key, value]) => [key, value.default])
	);

let tabId, options, enabled, editor;

function showOption(grid, name, def) {
	let label = document.createElement('label'),
		inputCnt = document.createElement('span'),
		input;

	if (!(def.show ?? true)) return;

	if (def.type === 'boolean') {
		input = document.createElement('input');

		input.type = 'checkbox';
		input.checked = options[name] ?? def.default;

		input.addEventListener('input', () => {
			options[name] = input.checked;

			chrome.storage.local.set({
				[name]: input.checked
			});

			applyOptions();
		});
	} else if (def.type === 'dropdown') {
		input = document.createElement('select');

		input.append(...def.values.map(({val, name: valName}) => {
			let option = document.createElement('option');

			if (val === (options[name] ?? def.default)) {
				option.selected = true;
			}

			option.innerText = valName;
			option.value = val;

			return option;
		}));

		input.addEventListener('input', () => {
			options[name] = input.value;

			chrome.storage.local.set({
				[name]: input.value
			});

			applyOptions();
		});
	}

	input.id = `opt-${name}`;
	label.innerText = def.desc;
	label.htmlFor = `opt-${name}`;

	inputCnt.append(input);
	grid.append(label, inputCnt);
}

function showOptions() {
	let popupEl = document.createElement('div'),
		close = document.createElement('button'),
		grid = document.createElement('div');

	for (let optionName in optionDefinitions) showOption(grid, optionName, optionDefinitions[optionName]);

	popupEl.className = 'option-popup';
	grid.className = 'option-grid';
	close.innerHTML = 'Close';

	close.addEventListener('click', () => popupEl.remove());

	popupEl.append(grid, close);
	document.body.append(popupEl);
}

async function getPageValue(name, def) {
	return (await chrome.scripting.executeScript({
		func: name => window[name],
		args: ['PAGE_VAL_' + name],
		target: {tabId}
	}))[0].result ?? def;
}

async function setPageValue(name, val) {
	return (await chrome.scripting.executeScript({
		func: (name, val) => window[name] = val,
		args: ['PAGE_VAL_' + name, val],
		target: {tabId}
	}))[0].result;
}

async function replacePageValue(name, val, def) {
	return (await chrome.scripting.executeScript({
		func: (name, val) => {
			let temp = window[name];
			window[name] = val;
			return temp;
		},
		args: ['PAGE_VAL_' + name, val],
		target: {tabId}
	}))[0].result ?? def;
}

function updateEnabledToggle() {
	document.getElementById(enabled ? 'enable' : 'disable').style.display = 'none';
	document.getElementById(enabled ? 'disable' : 'enable').style.display = '';
}

function toggleEnabled() {
	enabled = !enabled;

	updateEnabledToggle();
	setPageValue('enabled', enabled);
	applyCSS();
}

async function applyCSS() {
	let newCSS = enabled && editor.getValue(),
		prevCSS = await replacePageValue('prevInsertedCSS', newCSS);

	if (prevCSS === newCSS) return;

	if (newCSS)
		chrome.scripting.insertCSS({
			css: newCSS,
			target: {tabId}
		});

	if (prevCSS)
		chrome.scripting.removeCSS({
			css: prevCSS,
			target: {tabId}
		});
}

function applyOptions() {
	let darkMode = chrome.devtools
		? chrome.devtools.panels.themeName === 'dark'
		: options.popupColorScheme === 'dark' || (options.popupColorScheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

	editor.setTheme('ace/theme/' + (darkMode ? 'clouds_midnight' : 'clouds'));
	document.body.classList.toggle('dark', darkMode);

	editor.setOptions({
		enableBasicAutocompletion: options.autoComplete,
		enableSnippets: options.autoComplete,
		enableLiveAutocompletion: options.autoComplete,
		useSoftTabs: options.indentType !== 'tab',
		tabSize: options.indentType !== 'tab' && Number(options.indentType),
		wrap: options.wordWrap && 'free',
		scrollPastEnd: options.scrollPastEnd,
		showGutter: options.showGutter,
		useWorker: false
	});
}

async function initializeEditor() {
	editor.session.setMode('ace/mode/css');
	editor.renderer.setScrollMargin(5, 5);

	editor.on('change', () => {
		applyCSS();

		setPageValue('prevEditorCSS', editor.getValue());

		chrome.storage.local.set({
			prevEditorCSSGlobal: editor.getValue()
		});
	});

	let initialValue = (options.remember && options.prevEditorCSSGlobal) || '';

	editor.setValue(await getPageValue('prevEditorCSS', initialValue), 1);
	editor.resize();
}

function addButtonListeners() {
	document.getElementById('settings').addEventListener('click', showOptions);

	document.getElementById('disable').addEventListener('click', toggleEnabled);
	document.getElementById('enable').addEventListener('click', toggleEnabled);

	document.getElementById('download').addEventListener('click', () => {
		let downloader = document.createElement('a');

		downloader.download = 'my.css';
		downloader.href = URL.createObjectURL(new Blob([editor.getValue()], {type: 'text/css'}));
		document.body.append(downloader);
		downloader.click();

		URL.revokeObjectURL(downloader.href);
		downloader.remove();
	});

	document.getElementById('upload').addEventListener('click',  () => {
		let loader = document.createElement('input');

		loader.type = 'file';
		loader.style.display = 'none';

		loader.addEventListener('change', () => {
			let file = loader.files[0],
				reader = new FileReader();

			reader.addEventListener('load', () => editor.setValue(reader.result, 1));
			reader.readAsText(file);
		});

		document.body.append(loader);
		loader.click();
		loader.remove();
	});
}

async function initialize() {
	options = await chrome.storage.local.get({
		...optionDefaults,
		prevEditorCSSGlobal: ''
	});

	tabId = chrome.devtools?.inspectedWindow.tabId ?? (await chrome.tabs.query({
		active: true,
		currentWindow: true
	}))[0]?.id;

	if (!tabId)
		throw Error('Tab ID not available');

	enabled = await getPageValue('enabled', true);
	editor = ace.edit('editor');

	addButtonListeners();
	updateEnabledToggle();
	initializeEditor();
	applyOptions();

	chrome.tabs.onUpdated.addListener((updatedTabId, changeInfo) => {
		if (updatedTabId !== tabId) return;

		if (changeInfo.status === 'loading') applyCSS();
	});
}

if (!chrome.devtools)
	document.body.classList.add('popup');

initialize().catch(e => {
	document.getElementById('toolbar').innerHTML = e;
});
