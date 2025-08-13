classdef ConfigManager < handle
    properties
        App
        ConfigFile = 'signal_viewer_config.mat'
        DefaultConfigPath = ''
        LastSavedConfig = struct()
        AutoSaveEnabled = false
        AutoSaveInterval = 300  % 5 minutes in seconds
        AutoSaveTimer
    end

    methods
        function obj = ConfigManager(app)
            obj.App = app;
            obj.DefaultConfigPath = fullfile(pwd, obj.ConfigFile);
            obj.initializeAutoSave();
        end

        function initializeAutoSave(obj)
            % Initialize auto-save functionality
            if obj.AutoSaveEnabled
                obj.AutoSaveTimer = timer('ExecutionMode', 'fixedRate', ...
                    'Period', obj.AutoSaveInterval, ...
                    'TimerFcn', @(~,~) obj.autoSaveConfig());
                start(obj.AutoSaveTimer);
            end
        end

        function saveConfig(obj, customPath)
            % Enhanced save configuration - now handles optional customPath
            app = obj.App;

            if nargin < 2 || isempty(customPath)
                [file, path] = uiputfile('*.mat', 'Save Configuration', obj.ConfigFile);
                if isequal(file, 0), return; end
                customPath = fullfile(path, file);
            end

            try
                if ~obj.validateAppData()
                    app.StatusLabel.Text = '❌ Invalid application data - cannot save configuration';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                config = struct();

                % === CORE CONFIGURATION ===
                config.AssignedSignals = app.PlotManager.AssignedSignals;
                config.TabLayouts = app.PlotManager.TabLayouts;
                config.CurrentTabIdx = app.PlotManager.CurrentTabIdx;
                config.SelectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;
                config.NumTabs = numel(app.PlotManager.TabLayouts);

                % ADD THIS LINE:
                if isprop(app.PlotManager, 'CustomYLabels') && ~isempty(app.PlotManager.CustomYLabels)
                    config.CustomYLabels = app.PlotManager.CustomYLabels;
                else
                    config.CustomYLabels = containers.Map();
                end
                % === SIGNAL PROPERTIES ===
                config.SignalScaling = app.DataManager.SignalScaling;
                config.StateSignals = app.DataManager.StateSignals;

                % === UI STATE ===
                config.SubplotMetadata = app.safeGetProperty('SubplotMetadata', {});
                config.SignalStyles = app.safeGetProperty('SignalStyles', struct());
                config.SubplotCaptions = app.safeGetProperty('SubplotCaptions', {});
                config.SubplotDescriptions = app.safeGetProperty('SubplotDescriptions', {});
                config.SubplotTitles = app.safeGetProperty('SubplotTitles', {});
                config.ExpandedTreeNodes = app.safeGetProperty('ExpandedTreeNodes', string.empty);

                % === TAB CONTROLS STATE ===
                config.TabControlsData = {};
                try
                    if isprop(app.PlotManager, 'TabControls') && ~isempty(app.PlotManager.TabControls)
                        config.TabControlsData = cell(1, numel(app.PlotManager.TabControls));
                        for i = 1:numel(app.PlotManager.TabControls)
                            if ~isempty(app.PlotManager.TabControls{i})
                                config.TabControlsData{i} = struct(...
                                    'RowsValue', app.PlotManager.TabControls{i}.RowsSpinner.Value, ...
                                    'ColsValue', app.PlotManager.TabControls{i}.ColsSpinner.Value);
                            end
                        end
                    end
                catch
                    config.TabControlsData = {};
                end

                % === DERIVED SIGNALS ===
                if isprop(app, 'SignalOperations') && ~isempty(app.SignalOperations)
                    config.DerivedSignals = app.SignalOperations.DerivedSignals;
                    config.OperationHistory = app.SignalOperations.OperationHistory;
                    config.OperationCounter = app.SignalOperations.OperationCounter;
                end

                % === LINKING CONFIGURATION ===
                if isprop(app, 'LinkingManager') && ~isempty(app.LinkingManager)
                    config.LinkedGroups = app.LinkingManager.LinkedGroups;
                    config.AutoLinkEnabled = app.LinkingManager.AutoLinkEnabled;
                    config.LinkingMode = app.LinkingManager.LinkingMode;
                end

                % === METADATA ===
                config.ConfigVersion = '2.1';
                config.MatlabVersion = version();
                config.SaveTimestamp = datetime('now');

                if isfile(customPath)
                    obj.createBackup(customPath);
                end

                try
                    config.XAxisSignals = app.XAxisSignals;
                catch
                    config.XAxisSignals = {};
                end

                % === PER-TAB AXIS LINKING ===
                try
                    if isprop(app.PlotManager, 'TabLinkedAxes')
                        config.TabLinkedAxes = app.PlotManager.TabLinkedAxes;
                    else
                        config.TabLinkedAxes = [];
                    end
                catch
                    config.TabLinkedAxes = [];
                end

                config.TupleSignals = app.PlotManager.TupleSignals;
                config.TupleMode = app.PlotManager.TupleMode;

                save(customPath, 'config', '-v7.3');
                obj.LastSavedConfig = config;

                [~, fileName] = fileparts(customPath);
                app.StatusLabel.Text = sprintf('✅ Config saved: %s.mat', fileName);
                app.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.handleError(ME, 'Save failed');
            end

            app.restoreFocus();
        end

        function value = getOrDefault(obj, propName, defaultValue)
            % Safely get property value with default fallback
            if isprop(obj, propName) && ~isempty(obj.(propName))
                value = obj.(propName);
            else
                value = defaultValue;
            end
        end


        function showConfigLoadSummary(obj, config, isCompatible, missingSignals)
            % Show summary of configuration load results
            summary = sprintf('Configuration Load Summary:\n\n');
            summary = [summary sprintf('• Layout: %d tabs configured\n', numel(config.TabLayouts))];
            summary = [summary sprintf('• Compatibility: %s\n', char("Full" * isCompatible + "Partial" * (~isCompatible)))];
            if ~isempty(missingSignals)
                summary = [summary sprintf('• Missing Signals: %d\n', length(missingSignals))];
            end
            if isfield(config, 'DerivedSignals')
                summary = [summary sprintf('• Derived Signals: %d templates loaded\n', length(keys(config.DerivedSignals)))];
            end

            icon = char("success" * isCompatible + "warning" * (~isCompatible));
            uialert(obj.App.UIFigure, summary, 'Configuration Loaded', 'Icon', icon);
        end
        % Add to ConfigManager.m:
        function showCompatibilityDetails(obj, config, missingSignals, extraSignals)
            % Show detailed compatibility information
            details = sprintf('Configuration Compatibility Details:\n\n');
            details = [details sprintf('Config Version: %s\n', config.ConfigVersion)];
            details = [details sprintf('Config Signals: %d\n', config.SignalCount)];
            details = [details sprintf('Config Tabs: %d\n\n', config.TabCount)];

            if ~isempty(missingSignals)
                details = [details sprintf('Missing Signals (%d):\n', length(missingSignals))];
                for i = 1:min(10, length(missingSignals))  % Show max 10
                    details = [details sprintf('  • %s\n', missingSignals{i})];
                end
                if length(missingSignals) > 10
                    details = [details sprintf('  ... and %d more\n', length(missingSignals) - 10)];
                end
                details = [details newline];
            end

            if ~isempty(extraSignals)
                details = [details sprintf('Extra Signals (%d):\n', length(extraSignals))];
                for i = 1:min(5, length(extraSignals))  % Show max 5
                    details = [details sprintf('  • %s\n', extraSignals{i})];
                end
                if length(extraSignals) > 5
                    details = [details sprintf('  ... and %d more\n', length(extraSignals) - 5)];
                end
            end

            uialert(obj.App.UIFigure, details, 'Compatibility Details', 'Icon', 'info');
        end

        function autoSaveConfig(obj)
            % Automatic save functionality
            if obj.hasConfigChanged()
                try
                    autoSavePath = fullfile(pwd, 'autosave_config.mat');
                    obj.saveConfig(autoSavePath);
                    obj.App.StatusLabel.Text = '💾 Auto-saved';
                catch ME
                    fprintf('Auto-save failed: %s\n', ME.message);
                end
            end
        end

        function tf = hasConfigChanged(obj)
            % Check if configuration has changed since last save
            if isempty(obj.LastSavedConfig)
                tf = true;
                return;
            end

            try
                currentConfig = obj.buildConfigStruct();
                tf = ~isequal(currentConfig, obj.LastSavedConfig);
            catch
                tf = true;  % Assume changed if comparison fails
            end
        end

        function config = buildConfigStruct(obj)
            % Build configuration structure - settings only, no data
            app = obj.App;

            config = struct();

            % Plot manager data (layouts and assignments)
            config.AssignedSignals = app.PlotManager.AssignedSignals;
            config.TabLayouts = app.PlotManager.TabLayouts;
            config.CurrentTabIdx = app.PlotManager.CurrentTabIdx;
            config.SelectedSubplotIdx = app.PlotManager.SelectedSubplotIdx;

            % Per-tab axis linking
            if isprop(app.PlotManager, 'TabLinkedAxes')
                config.TabLinkedAxes = app.PlotManager.TabLinkedAxes;
            else
                config.TabLinkedAxes = [];
            end

            % Signal settings
            config.SignalScaling = app.DataManager.SignalScaling;
            config.StateSignals = app.DataManager.StateSignals;

            % App-level settings
            if isprop(app, 'SubplotMetadata')
                config.SubplotMetadata = app.SubplotMetadata;
            else
                config.SubplotMetadata = {};
            end

            if isprop(app, 'SignalStyles')
                config.SignalStyles = app.SignalStyles;
            else
                config.SignalStyles = struct();
            end
            config.SubplotCaptions = app.SubplotCaptions;
            config.SubplotDescriptions = app.SubplotDescriptions;
            % Metadata
            config.ConfigVersion = '2.0';
            config.SaveTimestamp = datetime('now');
        end
        function applyConfiguration(obj, config)
            app = obj.App;

            try
                % === APPLY SIGNAL SETTINGS FIRST ===
                if isfield(config, 'SignalScaling')
                    scaleKeys = keys(config.SignalScaling);
                    for i = 1:length(scaleKeys)
                        if ismember(scaleKeys{i}, app.DataManager.SignalNames)
                            app.DataManager.SignalScaling(scaleKeys{i}) = config.SignalScaling(scaleKeys{i});
                        end
                    end
                end

                if isfield(config, 'StateSignals')
                    stateKeys = keys(config.StateSignals);
                    for i = 1:length(stateKeys)
                        if ismember(stateKeys{i}, app.DataManager.SignalNames)
                            app.DataManager.StateSignals(stateKeys{i}) = config.StateSignals(stateKeys{i});
                        end
                    end
                end

                % === CREATE REQUIRED TABS ===
                if isfield(config, 'TabLayouts')
                    requiredTabs = numel(config.TabLayouts);

                    % Remove + tab temporarily
                    plusTabIdx = [];
                    for i = 1:numel(app.PlotManager.PlotTabs)
                        if strcmp(app.PlotManager.PlotTabs{i}.Title, '+')
                            plusTabIdx = i;
                            break;
                        end
                    end

                    if ~isempty(plusTabIdx)
                        delete(app.PlotManager.PlotTabs{plusTabIdx});
                        app.PlotManager.PlotTabs(plusTabIdx) = [];
                    end

                    % Create additional tabs if needed
                    while numel(app.PlotManager.PlotTabs) < requiredTabs
                        app.PlotManager.addNewTab();
                    end

                    % Apply layouts
                    app.PlotManager.TabLayouts = config.TabLayouts;

                    % Recreate each tab with proper layout
                    for tabIdx = 1:requiredTabs
                        layout = config.TabLayouts{tabIdx};
                        app.PlotManager.createSubplotsForTab(tabIdx, layout(1), layout(2));
                    end
                end

                % === RESTORE DERIVED SIGNALS ===
                if isfield(config, 'DerivedSignals') && isprop(app, 'SignalOperations')
                    app.SignalOperations.DerivedSignals = config.DerivedSignals;

                    derivedNames = keys(config.DerivedSignals);
                    for i = 1:length(derivedNames)
                        if ~ismember(derivedNames{i}, app.DataManager.SignalNames)
                            app.DataManager.SignalNames{end+1} = derivedNames{i};
                        end
                    end

                    if isfield(config, 'OperationHistory')
                        app.SignalOperations.OperationHistory = config.OperationHistory;
                    end
                    if isfield(config, 'OperationCounter')
                        app.SignalOperations.OperationCounter = config.OperationCounter;
                    end
                end

                % === RESTORE PLOT ASSIGNMENTS ===
                if isfield(config, 'AssignedSignals')
                    filteredAssignments = config.AssignedSignals;
                    for tabIdx = 1:numel(filteredAssignments)
                        for subplotIdx = 1:numel(filteredAssignments{tabIdx})
                            assignments = filteredAssignments{tabIdx}{subplotIdx};
                            validAssignments = {};
                            for i = 1:numel(assignments)
                                if isstruct(assignments{i}) && isfield(assignments{i}, 'Signal')
                                    if ismember(assignments{i}.Signal, app.DataManager.SignalNames)
                                        validAssignments{end+1} = assignments{i};
                                    end
                                end
                            end
                            filteredAssignments{tabIdx}{subplotIdx} = validAssignments;
                        end
                    end
                    app.PlotManager.AssignedSignals = filteredAssignments;
                end

                if isfield(config, 'TupleSignals')
                    app.PlotManager.TupleSignals = config.TupleSignals;
                else
                    app.PlotManager.TupleSignals = {};
                end

                if isfield(config, 'TupleMode')
                    app.PlotManager.TupleMode = config.TupleMode;
                else
                    app.PlotManager.TupleMode = {};
                end

                if isfield(config, 'CustomYLabels')
                    try
                        app.PlotManager.CustomYLabels = config.CustomYLabels;
                    catch
                        % Handle conversion issues
                        app.PlotManager.CustomYLabels = containers.Map();
                        if isstruct(config.CustomYLabels)
                            fieldNames = fieldnames(config.CustomYLabels);
                            for i = 1:length(fieldNames)
                                app.PlotManager.CustomYLabels(fieldNames{i}) = config.CustomYLabels.(fieldNames{i});
                            end
                        end
                    end
                else
                    % Initialize if not present
                    app.PlotManager.CustomYLabels = containers.Map();
                end

                % === RESTORE OTHER SETTINGS ===
                if isfield(config, 'CurrentTabIdx')
                    app.PlotManager.CurrentTabIdx = min(config.CurrentTabIdx, numel(app.PlotManager.PlotTabs));
                end

                if isfield(config, 'SelectedSubplotIdx')
                    app.PlotManager.SelectedSubplotIdx = config.SelectedSubplotIdx;
                end

                % === RESTORE UI STATE ===
                if isfield(config, 'SubplotMetadata')
                    app.SubplotMetadata = config.SubplotMetadata;
                end
                if isfield(config, 'SignalStyles')
                    app.SignalStyles = config.SignalStyles;
                end
                if isfield(config, 'SubplotCaptions')
                    app.SubplotCaptions = config.SubplotCaptions;
                end
                if isfield(config, 'SubplotDescriptions')
                    app.SubplotDescriptions = config.SubplotDescriptions;
                end
                if isfield(config, 'SubplotTitles')
                    app.SubplotTitles = config.SubplotTitles;
                end
                if isfield(config, 'ExpandedTreeNodes')
                    app.ExpandedTreeNodes = config.ExpandedTreeNodes;
                end

                % === RESTORE PER-TAB AXIS LINKING ===
                if isfield(config, 'TabLinkedAxes') && isprop(app.PlotManager, 'TabLinkedAxes')
                    app.PlotManager.TabLinkedAxes = config.TabLinkedAxes;

                    % Update the UI toggles to reflect the restored state
                    for i = 1:length(app.PlotManager.TabLinkedAxes)
                        if i <= length(app.PlotManager.TabControls) && ...
                                ~isempty(app.PlotManager.TabControls{i}) && ...
                                isfield(app.PlotManager.TabControls{i}, 'LinkAxesToggle')
                            app.PlotManager.TabControls{i}.LinkAxesToggle.Value = app.PlotManager.TabLinkedAxes(i);
                        end
                    end
                end


                % === FINALIZE ===
                app.buildSignalTree();

                % Refresh all tabs
                for tabIdx = 1:numel(app.PlotManager.TabLayouts)
                    app.PlotManager.refreshPlots(tabIdx);
                end

                % Apply per-tab axis linking after plots are refreshed
                for tabIdx = 1:length(app.PlotManager.TabLinkedAxes)
                    if app.PlotManager.TabLinkedAxes(tabIdx)
                        app.PlotManager.linkTabAxes(tabIdx);
                    end
                end

                app.PlotManager.ensurePlusTabAtEnd();
                app.PlotManager.updateTabTitles();

                obj.cleanupCustomYLabels();  % Clean up invalid references

            catch ME
                fprintf('Error applying configuration: %s\n', ME.message);
                app.StatusLabel.Text = ['❌ Configuration load failed: ' ME.message];
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        function cleanupCustomYLabels(obj)
            % Clean up custom Y-axis labels for non-existent subplots

            try
                if ~isprop(obj, 'CustomYLabels') || isempty(obj.CustomYLabels)
                    return;
                end

                % Get valid subplot keys
                validKeys = {};
                for tabIdx = 1:numel(obj.TabLayouts)
                    layout = obj.TabLayouts{tabIdx};
                    numSubplots = layout(1) * layout(2);
                    for subplotIdx = 1:numSubplots
                        validKeys{end+1} = sprintf('Tab%d_Plot%d', tabIdx, subplotIdx);
                    end
                end

                % Remove invalid keys
                currentKeys = keys(obj.CustomYLabels);
                for i = 1:length(currentKeys)
                    if ~ismember(currentKeys{i}, validKeys)
                        obj.CustomYLabels.remove(currentKeys{i});
                    end
                end

            catch ME
                fprintf('Warning: CustomYLabels cleanup failed: %s\n', ME.message);
            end
        end
        function recreateTabs(obj, config)
            % Recreate tabs based on configuration
            app = obj.App;

            if isfield(config, 'TabLayouts') && ~isempty(config.TabLayouts)
                for tabIdx = 1:numel(config.TabLayouts)
                    % Create tab if it doesn't exist
                    while tabIdx > numel(app.PlotManager.PlotTabs)
                        tab = uitab(app.MainTabGroup, 'Title', sprintf('Tab %d', tabIdx));
                        app.PlotManager.PlotTabs{end+1} = tab;
                    end

                    % Recreate subplot layout
                    layout = config.TabLayouts{tabIdx};
                    if numel(layout) >= 2
                        rows = layout(1);
                        cols = layout(2);
                        app.PlotManager.createSubplotsForTab(tabIdx, rows, cols);
                    end
                end
            end
        end

        function applyDataManagerConfig(obj, config)
            % Apply data manager configuration
            app = obj.App;

            if isfield(config, 'SignalNames')
                app.DataManager.SignalNames = config.SignalNames;
            end

            % Handle multi-CSV structure instead of single DataBuffer
            if isfield(config, 'DataTables')
                app.DataManager.DataTables = config.DataTables;
            end

            if isfield(config, 'CSVFilePaths')
                app.DataManager.CSVFilePaths = config.CSVFilePaths;
            end

            if isfield(config, 'SignalScaling')
                app.DataManager.SignalScaling = config.SignalScaling;
            end

            if isfield(config, 'StateSignals')
                app.DataManager.StateSignals = config.StateSignals;
            end
        end

        function applyPlotManagerConfig(obj, config)
            % Apply plot manager configuration
            app = obj.App;

            if isfield(config, 'AssignedSignals')
                app.PlotManager.AssignedSignals = config.AssignedSignals;
            end

            if isfield(config, 'TabLayouts')
                app.PlotManager.TabLayouts = config.TabLayouts;
            end

            if isfield(config, 'CurrentTabIdx')
                app.PlotManager.CurrentTabIdx = config.CurrentTabIdx;
            end

            if isfield(config, 'SelectedSubplotIdx')
                app.PlotManager.SelectedSubplotIdx = config.SelectedSubplotIdx;
            end
        end

        function applyUIConfig(obj, config)
            % Apply UI configuration
            app = obj.App;

            % Apply to current tab's controls instead of non-existent global spinners
            tabIdx = app.PlotManager.CurrentTabIdx;
            if tabIdx <= numel(app.PlotManager.TabControls) && ~isempty(app.PlotManager.TabControls{tabIdx})
                if isfield(config, 'RowsSpinnerValue')
                    app.PlotManager.TabControls{tabIdx}.RowsSpinner.Value = config.RowsSpinnerValue;
                end

                if isfield(config, 'ColsSpinnerValue')
                    app.PlotManager.TabControls{tabIdx}.ColsSpinner.Value = config.ColsSpinnerValue;
                end
            end

            % Handle app-level properties if they exist
            if isfield(config, 'SubplotMetadata')
                app.SubplotMetadata = config.SubplotMetadata;
            end

            if isfield(config, 'SignalStyles')
                app.SignalStyles = config.SignalStyles;
            end

            % Skip CSVPathField and AutoScaleCheckbox since they don't exist in your current UI
        end
        function tf = validateAppData(obj)
            % Validate application data before saving
            app = obj.App;
            tf = true;

            try
                % Check if essential objects exist
                if ~isvalid(app.DataManager) || ~isvalid(app.PlotManager)
                    tf = false;
                    return;
                end

                % Validate data types
                if ~iscell(app.DataManager.SignalNames)
                    tf = false;
                    return;
                end

                % Check DataTables instead of DataBuffer
                if ~iscell(app.DataManager.DataTables)
                    tf = false;
                    return;
                end

            catch
                tf = false;
            end
        end

        function tf = validateConfigVersion(~, config)
            % Validate configuration version compatibility
            tf = true;

            if ~isfield(config, 'ConfigVersion')
                tf = false;
                return;
            end

            % Add version-specific validation logic here
            currentVersion = '2.0';
            configVersion = config.ConfigVersion;

            % For now, accept all versions but warn for older ones
            if str2double(configVersion) < str2double(currentVersion)
                tf = false;  % Will trigger warning dialog
            end
        end

        function createBackup(~, filePath)
            % Create backup of existing configuration file
            try
                [path, name, ext] = fileparts(filePath);
                backupPath = fullfile(path, [name '_backup_' datestr(now, 'yyyymmdd_HHMMSS') ext]);
                copyfile(filePath, backupPath);
            catch ME
                warning('Could not create backup: %s', ME.message);
            end
        end

        function value = safeGet(~, source, defaultValue)
            % Safely get value with default fallback
            try
                if isempty(source)
                    value = defaultValue;
                else
                    value = source;
                end
            catch
                value = defaultValue;
            end
        end

        function handleError(obj, ME, context)
            % Centralized error handling
            app = obj.App;

            errorMsg = sprintf('%s: %s', context, ME.message);
            app.StatusLabel.Text = ['❌ ' errorMsg];
            app.StatusLabel.FontColor = [0.9 0.3 0.3];

            % Log error details
            fprintf('ConfigManager Error (%s):\n', context);
            fprintf('  Message: %s\n', ME.message);
            fprintf('  Stack:\n');
            for i = 1:numel(ME.stack)
                fprintf('    %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
            end
        end

        function offerRecoveryOptions(obj)
            % Offer recovery options when loading fails
            app = obj.App;

            answer = uiconfirm(app.UIFigure, ...
                'Failed to load configuration. Would you like to:', ...
                'Recovery Options', ...
                'Options', {'Load Default', 'Try Again', 'Cancel'}, ...
                'DefaultOption', 'Load Default');
            app.restoreFocus();

            switch answer
                case 'Load Default'
                    obj.loadDefaultConfig();
                case 'Try Again'
                    obj.loadConfig();
                case 'Cancel'
                    return;
            end
        end

        function loadConfig(obj, customPath)
            % Enhanced load configuration - now handles optional customPath
            app = obj.App;

            if nargin < 2 || isempty(customPath)
                [file, path] = uigetfile('*.mat', 'Load Configuration');
                if isequal(file, 0), return; end
                customPath = fullfile(path, file);
            end

            try
                if ~isfile(customPath)
                    app.StatusLabel.Text = '❌ Configuration file not found';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                if ~app.hasSignalsLoaded()
                    answer = uiconfirm(app.UIFigure, ...
                        'No CSV data loaded. Load CSV files first to apply this configuration.', ...
                        'No Data Loaded', ...
                        'Options', {'Load CSVs First', 'Load Config Only', 'Cancel'}, ...
                        'DefaultOption', 'Load CSVs First');

                    switch answer
                        case 'Load CSVs First'
                            app.UIController.loadMultipleCSVs();
                            app.restoreFocus();
                            return;
                        case 'Cancel'
                            app.restoreFocus();
                            return;
                    end
                end

                loaded = load(customPath);
                if ~isfield(loaded, 'config')
                    app.StatusLabel.Text = '❌ Invalid configuration file format';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                config = loaded.config;

                % === CHECK COMPATIBILITY ===
                [isCompatible, missingSignals, ~] = app.checkConfigCompatibility(config);

                if ~isCompatible && ~isempty(missingSignals)
                    answer = uiconfirm(app.UIFigure, ...
                        sprintf('Some configured signals are missing. Continue with partial loading?\n\nMissing: %s', ...
                        strjoin(missingSignals(1:min(5,end)), ', ')), ...
                        'Signal Compatibility', ...
                        'Options', {'Load Compatible Parts', 'Cancel'}, ...
                        'DefaultOption', 'Load Compatible Parts');

                    if strcmp(answer, 'Cancel')
                        app.restoreFocus();
                        return;
                    end
                end

                % === APPLY CONFIGURATION ===
                obj.applyConfiguration(config);

                [~, fileName] = fileparts(customPath);
                if isCompatible
                    app.StatusLabel.Text = sprintf('✅ Config loaded: %s.mat', fileName);
                else
                    app.StatusLabel.Text = sprintf('⚠️ Config partially loaded: %s.mat', fileName);
                end
                app.StatusLabel.FontColor = [0.2 0.6 0.9];


                if isfield(config, 'XAxisSignals')
                    app.PlotManager.XAxisSignals = config.XAxisSignals;
                end
            catch ME
                obj.handleError(ME, 'Load failed');
            end

            app.restoreFocus();
        end
        function loadDefaultConfig(obj)
            % Load default configuration
            try
                defaultConfig = obj.createDefaultConfig();
                obj.applyConfiguration(defaultConfig);
                obj.App.StatusLabel.Text = '🔄 Default config loaded';
                app.StatusLabel.Text = '✅ Default configuration loaded';
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
            catch ME
                obj.handleError(ME, 'Default config load failed');
            end
        end

        function config = createDefaultConfig(obj)
            % Create default configuration structure
            config = struct();
            config.SignalNames = {};
            config.DataBuffer = table();
            config.SignalScaling = containers.Map();
            config.StateSignals = containers.Map();
            config.AssignedSignals = {};
            config.TabLayouts = {[2, 1]};
            config.CurrentTabIdx = 1;
            config.SelectedSubplotIdx = 1;
            config.RowsSpinnerValue = 2;
            config.ColsSpinnerValue = 1;
            config.CSVPath = '';
            config.AutoScale = true;
            config.ConfigVersion = '2.0';
            config.SaveTimestamp = datetime('now');
        end

        function delete(obj)
            % Cleanup when object is destroyed
            if ~isempty(obj.AutoSaveTimer) && isvalid(obj.AutoSaveTimer)
                stop(obj.AutoSaveTimer);
                delete(obj.AutoSaveTimer);
            end
        end
    end
end