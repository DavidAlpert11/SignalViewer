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

        function applyConfiguration(obj, config)
            app = obj.App;

            if isempty(app) || ~isvalid(app)
                error('Invalid app reference in ConfigManager');
            end

            try
                % Apply signal settings with validation
                if isfield(config, 'SignalScaling') && isa(config.SignalScaling, 'containers.Map')
                    scaleKeys = keys(config.SignalScaling);
                    for i = 1:length(scaleKeys)
                        try
                            if ismember(scaleKeys{i}, app.DataManager.SignalNames)
                                app.DataManager.SignalScaling(scaleKeys{i}) = config.SignalScaling(scaleKeys{i});
                            end
                        catch ME
                            fprintf('Warning applying signal scaling for %s: %s\n', scaleKeys{i}, ME.message);
                        end
                    end
                end

                % Apply state signals with validation
                if isfield(config, 'StateSignals') && isa(config.StateSignals, 'containers.Map')
                    stateKeys = keys(config.StateSignals);
                    for i = 1:length(stateKeys)
                        try
                            if ismember(stateKeys{i}, app.DataManager.SignalNames)
                                app.DataManager.StateSignals(stateKeys{i}) = config.StateSignals(stateKeys{i});
                            end
                        catch ME
                            fprintf('Warning applying state signal for %s: %s\n', stateKeys{i}, ME.message);
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


            catch ME
                fprintf('Error applying configuration: %s\n', ME.message);
                app.StatusLabel.Text = ['❌ Configuration load failed: ' ME.message];
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
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

        function delete(obj)
            % Enhanced cleanup to prevent memory leaks
            try
                % Stop and clean up auto-save timer
                if ~isempty(obj.AutoSaveTimer) && isvalid(obj.AutoSaveTimer)
                    if strcmp(obj.AutoSaveTimer.Running, 'on')
                        stop(obj.AutoSaveTimer);
                    end
                    delete(obj.AutoSaveTimer);
                    obj.AutoSaveTimer = [];
                end

                % Clear configuration data
                obj.LastSavedConfig = struct();

                % Break circular reference to App (CRITICAL)
                obj.App = [];

            catch ME
                fprintf('Warning during ConfigManager cleanup: %s\n', ME.message);
            end
        end
    end
end