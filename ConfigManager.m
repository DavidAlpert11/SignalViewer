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
            % Save configuration with enhanced error handling and validation
            app = obj.App;

            if nargin < 2
                [file, path] = uiputfile('*.mat', 'Save Configuration', obj.ConfigFile);
                if isequal(file, 0), return; end
                customPath = fullfile(path, file);
            end

            try
                % Validate data before saving
                if ~obj.validateAppData()
                    app.StatusLabel.Text = '❌ Invalid application data. Cannot save configuration';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                config = obj.buildConfigStruct();

                % Create backup if file exists
                if isfile(customPath)
                    obj.createBackup(customPath);
                end

                % Save with version information
                config.ConfigVersion = '2.0';
                config.MatlabVersion = version();
                config.SaveTimestamp = datetime('now');

                save(customPath, 'config', '-v7.3');  % Use v7.3 for large data support

                % Store last saved config for comparison
                obj.LastSavedConfig = config;

                % Update status
                app.StatusLabel.Text = sprintf('✅ Config saved: %s', file);

            catch ME
                obj.handleError(ME, 'Save failed');
            end
            obj.App.restoreFocus();

        end

        function loadConfig(obj, customPath)
            % Load configuration with enhanced validation and error recovery
            app = obj.App;

            if nargin < 2
                [file, path] = uigetfile('*.mat', 'Load Configuration');
                if isequal(file, 0), return; end
                customPath = fullfile(path, file);
            end

            try
                % Validate file exists and is readable
                if ~isfile(customPath)
                    app.StatusLabel.Text = '❌ Configuration file not found';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                % CHECK 1: Do we have any data loaded?
                if ~app.hasSignalsLoaded()
                    answer = uiconfirm(app.UIFigure, ...
                        'No CSV data is currently loaded. Load CSV files first, then load the configuration.', ...
                        'No Data Loaded', ...
                        'Options', {'Load CSVs First', 'Cancel'}, ...
                        'DefaultOption', 'Load CSVs First');
                    app.restoreFocus();

                    if strcmp(answer, 'Load CSVs First')
                        app.UIController.loadMultipleCSVs();
                        return;
                    else
                        return;
                    end
                end

                % Load and validate config file format
                loaded = load(customPath);
                if ~isfield(loaded, 'config')
                    app.StatusLabel.Text = '❌ Invalid configuration file format';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                    app.restoreFocus();
                    return;
                end

                config = loaded.config;

                % CHECK 2: Are the signals compatible?
                [isCompatible, missingSignals, extraSignals] = app.checkConfigCompatibility(config);

                if ~isCompatible
                    % Show detailed compatibility report
                    missingStr = strjoin(missingSignals, ', ');
                    extraStr = strjoin(extraSignals, ', ');

                    msg = sprintf(['Signal mismatch detected:\n\n' ...
                        'Missing signals (in config but not loaded):\n%s\n\n' ...
                        'Extra signals (loaded but not in config):\n%s\n\n' ...
                        'Load a different CSV file or config?'], ...
                        missingStr, extraStr);

                    answer = uiconfirm(app.UIFigure, msg, 'Signal Mismatch', ...
                        'Options', {'Load Anyway (Partial)', 'Cancel'}, ...
                        'DefaultOption', 'Cancel');
                    app.restoreFocus();

                    if strcmp(answer, 'Cancel')
                        return;
                    end
                    % If "Load Anyway", continue with partial loading
                end

                % Apply configuration
                obj.applyConfiguration(config);

                % Show success message with compatibility info
                if isCompatible
                    app.StatusLabel.Text = sprintf('✅ Config loaded: %s', extractAfter(customPath, max(strfind(customPath, filesep))));
                else
                    app.StatusLabel.Text = sprintf('⚠️ Config partially loaded: %s', extractAfter(customPath, max(strfind(customPath, filesep))));
                end

            catch ME
                obj.handleError(ME, 'Load failed');
            end
            obj.App.restoreFocus();

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
            % Apply configuration with proper error handling and validation
            app = obj.App;

            try
                % Apply signal settings first
                if isfield(config, 'SignalScaling')
                    % Only apply scaling for signals that exist
                    scaleKeys = keys(config.SignalScaling);
                    for i = 1:length(scaleKeys)
                        if ismember(scaleKeys{i}, app.DataManager.SignalNames)
                            app.DataManager.SignalScaling(scaleKeys{i}) = config.SignalScaling(scaleKeys{i});
                        end
                    end
                end

                if isfield(config, 'StateSignals')
                    % Only apply state settings for signals that exist
                    stateKeys = keys(config.StateSignals);
                    for i = 1:length(stateKeys)
                        if ismember(stateKeys{i}, app.DataManager.SignalNames)
                            app.DataManager.StateSignals(stateKeys{i}) = config.StateSignals(stateKeys{i});
                        end
                    end
                end

                % Apply plot manager settings
                if isfield(config, 'TabLayouts')
                    app.PlotManager.TabLayouts = config.TabLayouts;
                    % Recreate tabs with proper layouts
                    for tabIdx = 1:numel(config.TabLayouts)
                        if tabIdx <= numel(app.PlotManager.PlotTabs)
                            layout = config.TabLayouts{tabIdx};
                            app.PlotManager.createSubplotsForTab(tabIdx, layout(1), layout(2));
                        end
                    end
                end

                if isfield(config, 'AssignedSignals')
                    % Filter out assignments for signals that don't exist
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

                if isfield(config, 'CurrentTabIdx')
                    app.PlotManager.CurrentTabIdx = min(config.CurrentTabIdx, numel(app.PlotManager.PlotTabs));
                end

                if isfield(config, 'SelectedSubplotIdx')
                    app.PlotManager.SelectedSubplotIdx = config.SelectedSubplotIdx;
                end

                % Apply app-level settings
                if isfield(config, 'SubplotMetadata')
                    app.SubplotMetadata = config.SubplotMetadata;
                end

                if isfield(config, 'SignalStyles')
                    app.SignalStyles = config.SignalStyles;
                end

                if isfield(config, 'SubplotMetadata')
                    app.SubplotMetadata = config.SubplotMetadata;
                end

                if isfield(config, 'SignalStyles')
                    app.SignalStyles = config.SignalStyles;
                end

                % ADD THESE LINES:
                if isfield(config, 'SubplotCaptions')
                    app.SubplotCaptions = config.SubplotCaptions;
                end

                if isfield(config, 'SubplotDescriptions')
                    app.SubplotDescriptions = config.SubplotDescriptions;
                end

                % Refresh the interface
                app.buildSignalTree();
                app.PlotManager.refreshPlots();

            catch ME
                fprintf('Error applying configuration: %s\n', ME.message);
                app.StatusLabel.Text = ['❌ Configuration load failed: ' ME.message];
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
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

        function tf = validateConfigVersion(obj, config)
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

        function createBackup(obj, filePath)
            % Create backup of existing configuration file
            try
                [path, name, ext] = fileparts(filePath);
                backupPath = fullfile(path, [name '_backup_' datestr(now, 'yyyymmdd_HHMMSS') ext]);
                copyfile(filePath, backupPath);
            catch ME
                warning('Could not create backup: %s', ME.message);
            end
        end

        function value = safeGet(obj, source, defaultValue)
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