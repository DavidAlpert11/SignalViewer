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
                    uialert(app.UIFigure, 'Invalid application data. Cannot save configuration.', 'Validation Error');
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
                uialert(app.UIFigure, 'Configuration saved successfully.', 'Success');
                
            catch ME
                obj.handleError(ME, 'Save failed');
            end
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
                    uialert(app.UIFigure, 'Configuration file not found.', 'File Error');
                    return;
                end
                
                % Load and validate config
                loaded = load(customPath);
                if ~isfield(loaded, 'config')
                    uialert(app.UIFigure, 'Invalid configuration file format.', 'Format Error');
                    return;
                end
                
                config = loaded.config;
                
                % Version compatibility check
                if ~obj.validateConfigVersion(config)
                    answer = uiconfirm(app.UIFigure, ...
                        'Configuration file may be from an older version. Continue loading?', ...
                        'Version Warning', 'Options', {'Yes', 'No'}, 'DefaultOption', 'No');
                    if strcmp(answer, 'No'), return; end
                end
                
                % Apply configuration with rollback capability
                obj.applyConfiguration(config);
                
                % Update UI status
                app.StatusLabel.Text = sprintf('✅ Config loaded: %s', file);
                uialert(app.UIFigure, 'Configuration loaded successfully.', 'Success');
                
            catch ME
                obj.handleError(ME, 'Load failed');
                obj.offerRecoveryOptions();
            end
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
            % Build configuration structure with validation
            app = obj.App;
            
            config = struct();
            
            % Core data - with null checks
            config.SignalNames = obj.safeGet(app.DataManager.SignalNames, {});
            config.DataBuffer = obj.safeGet(app.DataManager.DataBuffer, table());
            
            % Handle containers.Map objects safely
            if isa(app.DataManager.SignalScaling, 'containers.Map')
                config.SignalScaling = app.DataManager.SignalScaling;
            else
                config.SignalScaling = containers.Map();
            end
            
            if isa(app.DataManager.StateSignals, 'containers.Map')
                config.StateSignals = app.DataManager.StateSignals;
            else
                config.StateSignals = containers.Map();
            end
            
            % Plot manager data
            config.AssignedSignals = obj.safeGet(app.PlotManager.AssignedSignals, {});
            config.TabLayouts = obj.safeGet(app.PlotManager.TabLayouts, {});
            config.CurrentTabIdx = obj.safeGet(app.PlotManager.CurrentTabIdx, 1);
            config.SelectedSubplotIdx = obj.safeGet(app.PlotManager.SelectedSubplotIdx, 1);
            
            % UI settings
            config.RowsSpinnerValue = obj.safeGet(app.RowsSpinner.Value, 2);
            config.ColsSpinnerValue = obj.safeGet(app.ColsSpinner.Value, 1);
            config.CSVPath = obj.safeGet(app.CSVPathField.Value, '');
            config.AutoScale = obj.safeGet(app.AutoScaleCheckbox.Value, true);
            
            % Additional metadata
            config.AppVersion = '1.0';
            config.NumSignals = numel(config.SignalNames);
            config.NumDataPoints = height(config.DataBuffer);
        end
        
        function applyConfiguration(obj, config)
            % Apply configuration with proper error handling and validation
            app = obj.App;
            
            % Store current state for rollback
            currentState = obj.buildConfigStruct();
            
            try
                % Recreate tabs if necessary
                obj.recreateTabs(config);
                
                % Apply data manager settings
                obj.applyDataManagerConfig(config);
                
                % Apply plot manager settings
                obj.applyPlotManagerConfig(config);
                
                % Apply UI settings
                obj.applyUIConfig(config);
                
                % Refresh the interface
                app.UIController.updateSignalCheckboxes();
                app.PlotManager.refreshPlots();
                
                % Update visual enhancements
                if ismethod(app, 'updateSignalTableVisualFeedback')
                    app.updateSignalTableVisualFeedback();
                end
                
            catch ME
                % Rollback on error
                warning('Error applying configuration. Rolling back...');
                obj.applyConfiguration(currentState);
                rethrow(ME);
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
            
            if isfield(config, 'DataBuffer')
                app.DataManager.DataBuffer = config.DataBuffer;
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
            
            if isfield(config, 'RowsSpinnerValue')
                app.RowsSpinner.Value = config.RowsSpinnerValue;
            end
            
            if isfield(config, 'ColsSpinnerValue')
                app.ColsSpinner.Value = config.ColsSpinnerValue;
            end
            
            if isfield(config, 'CSVPath')
                app.CSVPathField.Value = config.CSVPath;
            end
            
            if isfield(config, 'AutoScale')
                app.AutoScaleCheckbox.Value = config.AutoScale;
            end
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
                
                if ~istable(app.DataManager.DataBuffer)
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
            uialert(app.UIFigure, errorMsg, 'Error');
            
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
                uialert(obj.App.UIFigure, 'Default configuration loaded.', 'Recovery');
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