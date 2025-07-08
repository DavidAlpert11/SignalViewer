classdef SignalViewerApp < matlab.apps.AppBase
    properties
        % Main UI
        UIFigure
        ControlPanel
        MainTabGroup

        % Enhanced color schemes
        Colors = [
            0.2 0.6 0.9;    % Blue
            0.9 0.3 0.3;    % Red
            0.3 0.8 0.4;    % Green
            0.9 0.6 0.2;    % Orange
            0.7 0.3 0.9;    % Purple
            0.2 0.9 0.8;    % Cyan
            0.9 0.8 0.2;    % Yellow
            0.9 0.4 0.7;    % Pink
            0.5 0.5 0.5;    % Gray
            0.1 0.1 0.9;    % Dark Blue
        ];

        % Controls
        RowsSpinner
        ColsSpinner
        SubplotDropdown
        SignalTable
        StartButton
        StopButton
        ClearButton
        ExportButton
        ExportPDFButton
        StatsButton
        ResetZoomButton
        CSVPathField
        AutoScaleCheckbox
        StatusLabel
        DataRateLabel
        
        % Tab Management Controls
        AddTabButton
        DeleteTabButton
        TabLayoutLabel
        TabRowsSpinner
        TabColsSpinner

        % Visual Enhancement Properties
        SubplotHighlightBoxes  % Array to store highlight boxes for each subplot
        CurrentHighlightColor = [0.2 0.8 0.4]  % Green highlight color

        % Subsystems
        PlotManager
        DataManager
        ConfigManager
        UIController
        SignalScaling
        StateSignals
        SaveConfigButton
        LoadConfigButton
    end

    methods
        function app = SignalViewerApp()
            %=== Create UI with modern styling ===%
            app.UIFigure = uifigure('Name', 'Signal Viewer Pro', ...
                'Position', [100 100 1200 800], ...
                       'Color', [0.3 0.3 0.3]);  % Dark theme background
                % 'Color', [0.15 0.15 0.15]);  % Dark theme background

            % Enhanced Control Panel with gradient-like styling
            app.ControlPanel = uipanel(app.UIFigure, ...
                'Title', 'Control Panel', ...
                'Position', [1 1 318 799], ...
                'BackgroundColor', [0.2 0.2 0.2], ...
                'ForegroundColor', [0.9 0.9 0.9], ...
                'BorderType', 'line', ...
                'BorderWidth', 2);

            % Main Tab Group with corrected properties (removed BackgroundColor)
            app.MainTabGroup = uitabgroup(app.UIFigure, ...
                'Position', [320 1 880 799]);

            %=== Create Enhanced Components ===%
            app.createEnhancedComponents();

            %=== Instantiate Subsystems ===%
            app.PlotManager = PlotManager(app);
            app.PlotManager.initialize();
            app.DataManager   = DataManager(app);
            app.ConfigManager = ConfigManager(app);
            app.UIController  = UIController(app);

            %=== Connect Callbacks ===%
            app.UIController.setupCallbacks();
            app.setupTabManagementCallbacks();
            
            %=== Initialize visual enhancements ===%
            app.initializeVisualEnhancements();
        end

        function createEnhancedComponents(app)
            % Enhanced layout with modern styling
            
            % Config buttons with gradient effect
            app.SaveConfigButton = uibutton(app.ControlPanel, 'Text', '💾 Save Config', ...
                'Position', [20 750 100 30], ...
                'BackgroundColor', [0.2 0.6 0.9], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');
            app.LoadConfigButton = uibutton(app.ControlPanel, 'Text', '📁 Load Config', ...
                'Position', [140 750 100 30], ...
                'BackgroundColor', [0.3 0.8 0.4], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');

            % Tab Management Section
            app.TabLayoutLabel = uilabel(app.ControlPanel, 'Text', 'Tab Management:', ...
                'Position', [20 710 120 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold', ...
                'FontSize', 12);

            % Add Tab Button with + icon
            app.AddTabButton = uibutton(app.ControlPanel, 'Text', '➕ Add Tab', ...
                'Position', [20 680 75 30], ...
                'BackgroundColor', [0.2 0.8 0.4], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold', ...
                'FontSize', 11, ...
                'Tooltip', 'Add a new tab with current layout settings');

            % Delete Tab Button with X icon
            app.DeleteTabButton = uibutton(app.ControlPanel, 'Text', '❌ Delete', ...
                'Position', [100 680 75 30], ...
                'BackgroundColor', [0.9 0.3 0.3], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold', ...
                'FontSize', 11, ...
                'Tooltip', 'Delete the current tab');

            % Tab Layout Configuration
            uilabel(app.ControlPanel, 'Text', 'New Tab Layout:', ...
                'Position', [185 685 100 22], ...
                'FontColor', [0.8 0.8 0.8], ...
                'FontWeight', 'bold', ...
                'FontSize', 10);

            app.TabRowsSpinner = uispinner(app.ControlPanel, ...
                'Position', [185 665 40 20], ...
                'Limits', [1 5], ...
                'Value', 2, ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1], ...
                'FontSize', 9, ...
                'Tooltip', 'Rows for new tabs');

            uilabel(app.ControlPanel, 'Text', 'x', ...
                'Position', [230 665 10 20], ...
                'FontColor', [0.8 0.8 0.8], ...
                'HorizontalAlignment', 'center');

            app.TabColsSpinner = uispinner(app.ControlPanel, ...
                'Position', [245 665 40 20], ...
                'Limits', [1 5], ...
                'Value', 1, ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1], ...
                'FontSize', 9, ...
                'Tooltip', 'Columns for new tabs');

            % Layout spinners with enhanced styling (moved down)
            uilabel(app.ControlPanel, 'Text', 'Current Tab Layout:', ...
                'Position', [20 640 120 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');

            uilabel(app.ControlPanel, 'Text', 'Rows:', ...
                'Position', [20 620 40 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');
            app.RowsSpinner = uispinner(app.ControlPanel, ...
                'Position', [60 620 50 22], ...
                'Limits', [1 10], ...
                'Value', 2, ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1]);

            uilabel(app.ControlPanel, 'Text', 'Cols:', ...
                'Position', [130 620 40 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');
            app.ColsSpinner = uispinner(app.ControlPanel, ...
                'Position', [170 620 50 22], ...
                'Limits', [1 10], ...
                'Value', 1, ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1]);

            % Subplot dropdown with enhanced styling (moved down)
            uilabel(app.ControlPanel, 'Text', 'Current Subplot:', ...
                'Position', [20 590 100 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');
            app.SubplotDropdown = uidropdown(app.ControlPanel, ...
                'Position', [130 590 110 22], ...
                'Items', {'Plot 1'}, ...
                'Value', 'Plot 1', ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1]);

            % Enhanced control buttons with icons and colors (moved down)
            app.StartButton = uibutton(app.ControlPanel, 'Text', '▶️ Start', ...
                'Position', [20 550 70 30], ...
                'BackgroundColor', [0.2 0.8 0.4], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');
            app.StopButton = uibutton(app.ControlPanel, 'Text', '⏹️ Stop', ...
                'Position', [100 550 70 30], ...
                'BackgroundColor', [0.9 0.3 0.3], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');
            app.ClearButton = uibutton(app.ControlPanel, 'Text', '🗑️ Clear', ...
                'Position', [180 550 70 30], ...
                'BackgroundColor', [0.6 0.4 0.2], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');

            % Export buttons with modern styling (moved down)
            app.ExportButton = uibutton(app.ControlPanel, 'Text', '📊 Export CSV', ...
                'Position', [20 510 110 30], ...
                'BackgroundColor', [0.7 0.3 0.9], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');
            app.ExportPDFButton = uibutton(app.ControlPanel, 'Text', '📄 Export PDF', ...
                'Position', [140 510 110 30], ...
                'BackgroundColor', [0.9 0.6 0.2], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');

            % Utility buttons (moved down)
            app.StatsButton = uibutton(app.ControlPanel, 'Text', '📈 Statistics', ...
                'Position', [20 470 110 30], ...
                'BackgroundColor', [0.2 0.9 0.8], ...
                'FontColor', [0.1 0.1 0.1], ...
                'FontWeight', 'bold');
            app.ResetZoomButton = uibutton(app.ControlPanel, 'Text', '🔍 Reset Zoom', ...
                'Position', [140 470 110 30], ...
                'BackgroundColor', [0.9 0.4 0.7], ...
                'FontColor', [1 1 1], ...
                'FontWeight', 'bold');

            % CSV Field with enhanced styling (moved down)
            uilabel(app.ControlPanel, 'Text', 'CSV Path:', ...
                'Position', [20 440 100 22], ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');
            app.CSVPathField = uieditfield(app.ControlPanel, 'text', ...
                'Position', [20 420 260 22], ...
                'BackgroundColor', [0.3 0.3 0.3], ...
                'FontColor', [1 1 1]);

            % Auto scale checkbox with enhanced styling (moved down)
            app.AutoScaleCheckbox = uicheckbox(app.ControlPanel, ...
                'Text', '🔄 Auto Scale', ...
                'Position', [20 390 120 22], ...
                'Value', true, ...
                'FontColor', [0.9 0.9 0.9], ...
                'FontWeight', 'bold');

            % Status labels with enhanced styling (moved down)
            app.StatusLabel = uilabel(app.ControlPanel, ...
                'Text', '🟢 Ready', ...
                'Position', [20 360 260 22], ...
                'FontColor', [0.2 0.8 0.4], ...
                'FontWeight', 'bold');
            app.DataRateLabel = uilabel(app.ControlPanel, ...
                'Text', '📊 Data Rate: 0 Hz', ...
                'Position', [20 340 260 22], ...
                'FontColor', [0.7 0.7 0.7], ...
                'FontWeight', 'bold');

            % Enhanced Signal Table with modern styling (moved down and made smaller)
            app.SignalTable = uitable(app.ControlPanel, ...
                'Position', [20 20 280 310], ...
                'ColumnName', {'Signal', 'Info', 'Plot', 'Scale', 'State'}, ...
                'ColumnEditable', [false false true true true], ...
                'BackgroundColor', [0.25 0.25 0.25; 0.3 0.3 0.3], ...
                'ForegroundColor', [0.9 0.9 0.9]);
        end

        function setupTabManagementCallbacks(app)
            % Setup callbacks for tab management buttons
            app.AddTabButton.ButtonPushedFcn = @(src, event) app.addNewTab();
            app.DeleteTabButton.ButtonPushedFcn = @(src, event) app.deleteCurrentTab();
            
            % Setup callbacks for layout changes
            app.RowsSpinner.ValueChangedFcn = @(src, event) app.updateCurrentTabLayout();
            app.ColsSpinner.ValueChangedFcn = @(src, event) app.updateCurrentTabLayout();
            
            % Setup tab group selection callback
            app.MainTabGroup.SelectionChangedFcn = @(src, event) app.onTabSelectionChanged();
        end

        function addNewTab(app)
            % Add a new tab using the specified layout
            rows = app.TabRowsSpinner.Value;
            cols = app.TabColsSpinner.Value;
            
            % Add tab through PlotManager
            app.PlotManager.addNewTab(rows, cols);
            
            % Update UI feedback
            app.StatusLabel.Text = sprintf('🟢 Added new tab with %dx%d layout', rows, cols);
            app.StatusLabel.FontColor = [0.2 0.8 0.4];
            
            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function deleteCurrentTab(app)
            % Delete the current tab
            if numel(app.PlotManager.PlotTabs) <= 1
                app.StatusLabel.Text = '⚠️ Cannot delete the last tab';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end
            
            % Delete tab through PlotManager
            app.PlotManager.deleteCurrentTab();
            
            % Update UI feedback
            app.StatusLabel.Text = '🗑️ Tab deleted';
            app.StatusLabel.FontColor = [0.9 0.3 0.3];
            
            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function updateCurrentTabLayout(app)
            % Update the layout of the current tab
            rows = app.RowsSpinner.Value;
            cols = app.ColsSpinner.Value;
            
            % Update layout through PlotManager
            app.PlotManager.changeTabLayout(app.PlotManager.CurrentTabIdx, rows, cols);
            
            % Update UI feedback
            app.StatusLabel.Text = sprintf('🔄 Updated tab layout to %dx%d', rows, cols);
            app.StatusLabel.FontColor = [0.2 0.9 0.8];
            
            % Update subplot dropdown
            app.updateSubplotDropdown();
        end

        function onTabSelectionChanged(app)
            % Handle tab selection changes
            selectedTab = app.MainTabGroup.SelectedTab;
            
            % Find which tab index was selected
            for i = 1:numel(app.PlotManager.PlotTabs)
                if app.PlotManager.PlotTabs{i} == selectedTab
                    app.PlotManager.CurrentTabIdx = i;
                    app.PlotManager.SelectedSubplotIdx = 1;
                    
                    % Update UI to reflect current tab layout
                    if i <= numel(app.PlotManager.TabLayouts)
                        layout = app.PlotManager.TabLayouts{i};
                        app.RowsSpinner.Value = layout(1);
                        app.ColsSpinner.Value = layout(2);
                    end
                    
                    % Update subplot dropdown
                    app.updateSubplotDropdown();
                    
                    % Highlight first subplot
                    app.highlightSelectedSubplot(i, 1);
                    break;
                end
            end
        end

        function updateSubplotDropdown(app)
            % Update the subplot dropdown based on current tab layout
            if app.PlotManager.CurrentTabIdx <= numel(app.PlotManager.TabLayouts)
                layout = app.PlotManager.TabLayouts{app.PlotManager.CurrentTabIdx};
                numPlots = layout(1) * layout(2);
                
                % Create dropdown items
                items = cell(numPlots, 1);
                for i = 1:numPlots
                    items{i} = sprintf('Plot %d', i);
                end
                
                app.SubplotDropdown.Items = items;
                app.SubplotDropdown.Value = sprintf('Plot %d', app.PlotManager.SelectedSubplotIdx);
            end
        end

        function initializeVisualEnhancements(app)
            % Initialize subplot highlight system
            app.SubplotHighlightBoxes = {};
            
            % Set up enhanced visual feedback
            app.setupSubplotHighlighting();
        end

        function setupSubplotHighlighting(app)
            % This will be called when subplots are created to add visual feedback
            % The actual highlighting will be implemented in PlotManager
        end

        function highlightSelectedSubplot(app, tabIdx, subplotIdx)
            % Highlight the currently selected subplot with a colored border
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
               ~isempty(app.PlotManager.AxesArrays{tabIdx}) && ...
               subplotIdx <= numel(app.PlotManager.AxesArrays{tabIdx})
                
                % Clear previous highlights
                app.clearSubplotHighlights(tabIdx);
                
                % Add highlight to selected subplot
                ax = app.PlotManager.AxesArrays{tabIdx}(subplotIdx);
                if isvalid(ax)
                    % Create a visual highlight by changing the axis box color
                    ax.XColor = app.CurrentHighlightColor;
                    ax.YColor = app.CurrentHighlightColor;
                    ax.LineWidth = 3;
                    
                    % Add a title indicator
                    originalTitle = ax.Title.String;
                    if ~contains(originalTitle, '★')
                        ax.Title.String = sprintf('★ %s', originalTitle);
                        ax.Title.Color = app.CurrentHighlightColor;
                        ax.Title.FontWeight = 'bold';
                    end
                end
            end
        end

        function clearSubplotHighlights(app, tabIdx)
            % Clear all subplot highlights for a given tab
            if tabIdx <= numel(app.PlotManager.AxesArrays) && ...
               ~isempty(app.PlotManager.AxesArrays{tabIdx})
                
                for i = 1:numel(app.PlotManager.AxesArrays{tabIdx})
                    ax = app.PlotManager.AxesArrays{tabIdx}(i);
                    if isvalid(ax)
                        % Reset to default styling
                        ax.XColor = [0.7 0.7 0.7];
                        ax.YColor = [0.7 0.7 0.7];
                        ax.LineWidth = 1;
                        
                        % Remove star from title
                        originalTitle = ax.Title.String;
                        if contains(originalTitle, '★')
                            ax.Title.String = strrep(originalTitle, '★ ', '');
                            ax.Title.Color = [0.9 0.9 0.9];
                            ax.Title.FontWeight = 'normal';
                        end
                    end
                end
            end
        end

        function updateSignalTableVisualFeedback(app)
            % Update the signal table with visual feedback for plotted signals
            if ~isempty(app.SignalTable.Data)
                data = app.SignalTable.Data;
                
                % Create visual feedback in the table
                for i = 1:height(data)
                    if data.Plot(i)  % If signal is plotted
                        % Add visual indicators for plotted signals
                        originalSignal = data.Signal{i};
                        % Clean the signal name first
                        cleanSignal = strrep(strrep(originalSignal, '● ', ''), '○ ', '');
                        data.Signal{i} = sprintf('● %s', cleanSignal);
                    else
                        % Add indicator for unplotted signals
                        originalSignal = data.Signal{i};
                        % Clean the signal name first
                        cleanSignal = strrep(strrep(originalSignal, '● ', ''), '○ ', '');
                        data.Signal{i} = sprintf('○ %s', cleanSignal);
                    end
                end
                
                app.SignalTable.Data = data;
            end
        end
        
        function delete(app)
            % Delete app
            delete(app.UIFigure);
        end
    end
end