classdef SignalOperationsManager < handle
    properties
        App
        DerivedSignals          % containers.Map - stores computed signals
        OperationHistory        % cell array - tracks operations for undo
        InterpolationMethod     % string - interpolation method for multi-signal ops
        MaxHistorySize          % maximum number of operations to keep in history
        OperationCounter        % counter for unique operation IDs
    end

    methods
        function obj = SignalOperationsManager(app)
            obj.App = app;
            obj.DerivedSignals = containers.Map('KeyType', 'char', 'ValueType', 'any');
            obj.OperationHistory = {};
            obj.InterpolationMethod = 'linear';
            obj.MaxHistorySize = 50;
            obj.OperationCounter = 0;
        end

        %% =================================================================
        %% SINGLE SIGNAL OPERATIONS
        %% =================================================================

        function showSingleSignalDialog(obj, operationType)
            % Create dialog for single signal operations
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 450 300], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 410 25], ...
                'String', sprintf('Compute %s of Signal', operationType), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');
            signalNames = obj.getAllAvailableSignals();
            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 220 250 25], 'String', signalNames);

            % Method selection (operation-specific)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Method:', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'derivative'
                    methods = {'Gradient (recommended)', 'Forward Difference', 'Backward Difference', 'Central Difference'};
                    defaultMethod = 1;
                case 'integral'
                    methods = {'Cumulative Trapezoidal', 'Cumulative Simpson', 'Running Sum'};
                    defaultMethod = 1;
                otherwise
                    methods = {'Default'};
                    defaultMethod = 1;
            end

            methodDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 180 250 25], 'String', methods, 'Value', defaultMethod);

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 140 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            % Use curly braces to prevent subscript interpretation
            defaultName = sprintf('%s_{%s}', signalNames{1}, lower(operationType));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 140 250 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Update name when signal changes
            signalDropdown.Callback = @(src, ~) updateDefaultName();

            % Options (operation-specific)
            optionsPanel = uipanel('Parent', d, 'Position', [20 60 410 70], ...
                'Title', 'Options', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'derivative'
                    smoothingCheck = uicontrol('Parent', optionsPanel, 'Style', 'checkbox', ...
                        'Position', [10 30 200 20], 'String', 'Apply smoothing filter', 'Value', 0);
                    windowSizeLabel = uicontrol('Parent', optionsPanel, 'Style', 'text', ...
                        'Position', [10 5 100 20], 'String', 'Window size:');
                    windowSizeEdit = uicontrol('Parent', optionsPanel, 'Style', 'edit', ...
                        'Position', [120 5 50 20], 'String', '5', 'Enable', 'off');

                    smoothingCheck.Callback = @(src, ~) set(windowSizeEdit, 'Enable', ...
                        char("on" * src.Value + "off" * (1-src.Value)));

                case 'integral'
                    initialValueCheck = uicontrol('Parent', optionsPanel, 'Style', 'checkbox', ...
                        'Position', [10 30 200 20], 'String', 'Set initial value', 'Value', 0);
                    initialValueLabel = uicontrol('Parent', optionsPanel, 'Style', 'text', ...
                        'Position', [10 5 100 20], 'String', 'Initial value:');
                    initialValueEdit = uicontrol('Parent', optionsPanel, 'Style', 'edit', ...
                        'Position', [120 5 50 20], 'String', '0', 'Enable', 'off');

                    initialValueCheck.Callback = @(src, ~) set(initialValueEdit, 'Enable', ...
                        char("on" * src.Value + "off" * (1-src.Value)));
            end

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [250 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [340 15 80 30], 'Callback', @(~,~) close(d));

            function updateDefaultName()
                selectedSignal = signalNames{signalDropdown.Value};
                newName = sprintf('%s_{%s}', selectedSignal, lower(operationType));
                nameField.String = newName;
            end

            function computeAndClose()
                % try
                params = struct();
                params.SignalName = signalNames{signalDropdown.Value};
                params.Method = methods{methodDropdown.Value};
                params.ResultName = strtrim(nameField.String);

                % Add operation-specific parameters
                switch lower(operationType)
                    case 'derivative'
                        params.ApplySmoothing = smoothingCheck.Value;
                        if params.ApplySmoothing
                            params.WindowSize = str2double(windowSizeEdit.String);
                        end
                    case 'integral'
                        params.SetInitialValue = initialValueCheck.Value;
                        if params.SetInitialValue
                            params.InitialValue = str2double(initialValueEdit.String);
                        end
                end

                % Validate inputs
                if isempty(params.ResultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                % if obj.DerivedSignals.isKey(params.ResultName)
                %     answer = uiconfirm(d, sprintf('Signal "%s" already exists. Overwrite?', params.ResultName), ...
                %         'Confirm Overwrite', 'Options', {'Yes', 'No'}, 'DefaultOption', 'No');
                %     if strcmp(answer, 'No')
                %         return;
                %     end
                % end

                % Execute operation
                obj.executeSingleSignalOperation(operationType, params);
                close(d);

                % catch ME
                %     uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                % end
            end
        end

        function executeSingleSignalOperation(obj, operationType, params)
            % Get signal data
            [timeData, signalData, sourceInfo] = obj.getSignalData(params.SignalName);
            if isempty(timeData)
                error('Signal "%s" not found or empty.', params.SignalName);
            end

            % Perform operation
            switch lower(operationType)
                case 'derivative'
                    result = obj.computeDerivative(timeData, signalData, params);
                case 'integral'
                    result = obj.computeIntegral(timeData, signalData, params);
                otherwise
                    error('Unknown operation: %s', operationType);
            end

            % Create operation record
            operation = struct();
            operation.ID = obj.getNextOperationID();
            operation.Type = 'single';
            operation.Operation = operationType;
            operation.Timestamp = datetime('now');
            operation.InputSignals = {params.SignalName};
            operation.OutputSignal = params.ResultName;
            operation.Parameters = params;
            operation.SourceInfo = sourceInfo;

            % Store result
            obj.storeDerivedSignal(params.ResultName, result.Time, result.Data, operation);

            % Update UI
            obj.App.StatusLabel.Text = sprintf('✅ Created %s: %s', operationType, params.ResultName);
            obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function result = computeDerivative(~, timeData, signalData, params)
            % Compute numerical derivative
            result = struct();

            switch params.Method
                case 'Gradient (recommended)'
                    % Use MATLAB's gradient function (most accurate)
                    dt = mean(diff(timeData));
                    derivData = gradient(signalData, dt);

                case 'Forward Difference'
                    derivData = [0; diff(signalData) ./ diff(timeData)];

                case 'Backward Difference'
                    derivData = [diff(signalData) ./ diff(timeData); 0];

                case 'Central Difference'
                    n = length(signalData);
                    derivData = zeros(n, 1);
                    derivData(1) = (signalData(2) - signalData(1)) / (timeData(2) - timeData(1));
                    derivData(n) = (signalData(n) - signalData(n-1)) / (timeData(n) - timeData(n-1));
                    derivData(2:n-1) = (signalData(3:n) - signalData(1:n-2)) ./ (timeData(3:n) - timeData(1:n-2));
            end

            % Apply smoothing if requested
            if isfield(params, 'ApplySmoothing') && params.ApplySmoothing
                windowSize = params.WindowSize;
                if windowSize > 1 && windowSize < length(derivData)
                    derivData = smooth(derivData, windowSize);
                end
            end

            result.Time = timeData;
            result.Data = derivData;
        end

        function result = computeIntegral(~, timeData, signalData, params)
            % Compute numerical integral
            result = struct();

            switch params.Method
                case 'Cumulative Trapezoidal'
                    integralData = cumtrapz(timeData, signalData);

                case 'Cumulative Simpson'
                    % Use Simpson's rule (requires odd number of points)
                    if mod(length(signalData), 2) == 0
                        % Add one point by interpolation
                        timeData = [timeData; timeData(end) + (timeData(end) - timeData(end-1))];
                        signalData = [signalData; signalData(end)];
                    end
                    integralData = cumtrapz(timeData, signalData); % Fallback to trapezoidal

                case 'Running Sum'
                    dt = mean(diff(timeData));
                    integralData = cumsum(signalData) * dt;
            end

            % Apply initial value if requested
            if isfield(params, 'SetInitialValue') && params.SetInitialValue
                integralData = integralData + params.InitialValue;
            end

            result.Time = timeData;
            result.Data = integralData;
        end

        %% =================================================================
        %% MULTI-SIGNAL OPERATIONS
        %% =================================================================

        function showMultiSignalDialog(obj, operationType)
            % Create dialog for multi-signal operations
            switch lower(operationType)
                case {'subtract', 'add', 'multiply', 'divide'}
                    obj.showDualSignalDialog(operationType);
                case 'norm'
                    obj.showNormDialog();
                otherwise
                    error('Unknown multi-signal operation: %s', operationType);
            end
        end

        function showDualSignalDialog(obj, operationType)
            % Dialog for two-signal operations (subtract, add, etc.)
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 500 350], 'Resize', 'off');

            % Title
            opSymbols = containers.Map({'subtract', 'add', 'multiply', 'divide'}, ...
                {'−', '+', '×', '÷'});
            opSymbol = opSymbols(lower(operationType));

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 310 460 25], ...
                'String', sprintf('Signal A %s Signal B', opSymbol), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            signalNames = obj.getAllAvailableSignals();

            % Signal A selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 270 120 20], ...
                'String', 'Signal A:', 'FontWeight', 'bold');
            signalADropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 270 250 25], 'String', signalNames);

            % Signal B selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 120 20], ...
                'String', 'Signal B:', 'FontWeight', 'bold');
            signalBDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 230 250 25], 'String', signalNames, 'Value', min(2, length(signalNames)));

            % Interpolation options
            interpPanel = uipanel('Parent', d, 'Position', [20 140 460 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)', 'Signal A range', 'Signal B range'}, ...
                'Value', 1);

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            % Use curly braces to prevent subscript interpretation
            defaultName = sprintf('%s_{%s}_%s', signalNames{1}, lower(operationType), signalNames{min(2, end)});
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 100 250 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Update name when signals change
            updateName = @(~,~) set(nameField, 'String', sprintf('%s_{%s}_%s', ...
                signalNames{signalADropdown.Value}, lower(operationType), signalNames{signalBDropdown.Value}));
            signalADropdown.Callback = updateName;
            signalBDropdown.Callback = updateName;

            % Preview button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Preview', ...
                'Position', [150 50 80 30], 'Callback', @(~,~) showPreview());

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [320 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [410 15 80 30], 'Callback', @(~,~) close(d));

            function showPreview()
                % Show preview of time alignment
                try
                    signalA = signalNames{signalADropdown.Value};
                    signalB = signalNames{signalBDropdown.Value};

                    [timeA, dataA] = obj.getSignalData(signalA);
                    [timeB, dataB] = obj.getSignalData(signalB);

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    interpMethod = interpMethods{interpDropdown.Value};

                    [commonTime, alignedA, alignedB] = obj.alignTwoSignals(timeA, dataA, timeB, dataB, ...
                        interpMethod, rangeDropdown.Value);

                    % Create preview figure
                    fig = figure('Name', 'Signal Alignment Preview', 'Position', [100 100 800 600]);

                    subplot(3,1,1);
                    plot(timeA, dataA, 'b-', 'LineWidth', 1.5); hold on;
                    plot(timeB, dataB, 'r-', 'LineWidth', 1.5);
                    legend({signalA, signalB}, 'Location', 'best');
                    title('Original Signals');
                    grid on;

                    subplot(3,1,2);
                    plot(commonTime, alignedA, 'b-', 'LineWidth', 1.5); hold on;
                    plot(commonTime, alignedB, 'r-', 'LineWidth', 1.5);
                    legend({[signalA ' (aligned)'], [signalB ' (aligned)']}, 'Location', 'best');
                    title('Aligned Signals');
                    grid on;

                    subplot(3,1,3);
                    switch lower(operationType)
                        case 'subtract'
                            resultData = alignedA - alignedB;
                            opStr = sprintf('%s - %s', signalA, signalB);
                        case 'add'
                            resultData = alignedA + alignedB;
                            opStr = sprintf('%s + %s', signalA, signalB);
                        case 'multiply'
                            resultData = alignedA .* alignedB;
                            opStr = sprintf('%s × %s', signalA, signalB);
                        case 'divide'
                            resultData = alignedA ./ alignedB;
                            opStr = sprintf('%s ÷ %s', signalA, signalB);
                    end
                    plot(commonTime, resultData, 'g-', 'LineWidth', 2);
                    title(sprintf('Result: %s', opStr));
                    grid on;

                catch ME
                    uialert(d, sprintf('Preview error: %s', ME.message), 'Preview Failed');
                end
            end

            function computeAndClose()
                try
                    params = struct();
                    params.SignalA = signalNames{signalADropdown.Value};
                    params.SignalB = signalNames{signalBDropdown.Value};
                    params.ResultName = strtrim(nameField.String);

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    params.InterpolationMethod = interpMethods{interpDropdown.Value};
                    params.TimeRange = rangeDropdown.Value;

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    if strcmp(params.SignalA, params.SignalB)
                        uialert(d, 'Please select different signals for A and B.', 'Invalid Input');
                        return;
                    end

                    if obj.DerivedSignals.isKey(params.ResultName)
                        answer = uiconfirm(d, sprintf('Signal "%s" already exists. Overwrite?', params.ResultName), ...
                            'Confirm Overwrite', 'Options', {'Yes', 'No'}, 'DefaultOption', 'No');
                        if strcmp(answer, 'No')
                            return;
                        end
                    end

                    % Execute operation
                    obj.executeDualSignalOperation(operationType, params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function showNormDialog(obj)
            % Dialog for norm operation (multiple signals)
            d = dialog('Name', 'Norm Operation', 'Position', [300 300 500 400], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 460 25], ...
                'String', 'Compute Norm of Multiple Signals', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 330 120 20], ...
                'String', 'Select Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [150 260 250 70], 'String', signalNames, 'Max', length(signalNames));

            % Norm type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                'String', 'Norm Type:', 'FontWeight', 'bold');
            normDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 220 150 25], ...
                'String', {'L1 (Manhattan)', 'L2 (Euclidean)', 'L∞ (Maximum)'}, 'Value', 2);

            % Interpolation options
            interpPanel = uipanel('Parent', d, 'Position', [20 120 460 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)'}, 'Value', 1);

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 80 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 80 250 25], 'String', 'signals_{norm}', ...
                'HorizontalAlignment', 'left');
            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [320 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [410 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    selectedIndices = signalListbox.Value;
                    if length(selectedIndices) < 2
                        uialert(d, 'Please select at least 2 signals.', 'Invalid Selection');
                        return;
                    end

                    params = struct();
                    params.SelectedSignals = signalNames(selectedIndices);
                    params.ResultName = strtrim(nameField.String);
                    params.NormType = normDropdown.Value;

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    params.InterpolationMethod = interpMethods{interpDropdown.Value};
                    params.TimeRange = rangeDropdown.Value;

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    if obj.DerivedSignals.isKey(params.ResultName)
                        answer = uiconfirm(d, sprintf('Signal "%s" already exists. Overwrite?', params.ResultName), ...
                            'Confirm Overwrite', 'Options', {'Yes', 'No'}, 'DefaultOption', 'No');
                        if strcmp(answer, 'No')
                            return;
                        end
                    end

                    % Execute operation
                    obj.executeNormOperation(params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function executeDualSignalOperation(obj, operationType, params)
            % Execute dual signal operation (subtract, add, multiply, divide)
            [timeA, dataA, sourceInfoA] = obj.getSignalData(params.SignalA);
            [timeB, dataB, sourceInfoB] = obj.getSignalData(params.SignalB);

            if isempty(timeA) || isempty(timeB)
                error('One or both signals not found or empty.');
            end

            % Align signals
            [commonTime, alignedA, alignedB] = obj.alignTwoSignals(timeA, dataA, timeB, dataB, ...
                params.InterpolationMethod, params.TimeRange);

            % Perform operation
            switch lower(operationType)
                case 'subtract'
                    resultData = alignedA - alignedB;
                case 'add'
                    resultData = alignedA + alignedB;
                case 'multiply'
                    resultData = alignedA .* alignedB;
                case 'divide'
                    resultData = alignedA ./ alignedB;
                    % Handle division by zero
                    resultData(~isfinite(resultData)) = NaN;
                otherwise
                    error('Unknown operation: %s', operationType);
            end

            % Create operation record
            operation = struct();
            operation.ID = obj.getNextOperationID();
            operation.Type = 'dual';
            operation.Operation = operationType;
            operation.Timestamp = datetime('now');
            operation.InputSignals = {params.SignalA, params.SignalB};
            operation.OutputSignal = params.ResultName;
            operation.Parameters = params;
            operation.SourceInfo = {sourceInfoA, sourceInfoB};

            % Store result
            obj.storeDerivedSignal(params.ResultName, commonTime, resultData, operation);

            % Update UI
            obj.App.StatusLabel.Text = sprintf('✅ Created %s: %s', operationType, params.ResultName);
            obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        function executeNormOperation(obj, params)
            % Execute norm operation on multiple signals
            signalData = cell(length(params.SelectedSignals), 1);
            timeData = cell(length(params.SelectedSignals), 1);
            sourceInfos = cell(length(params.SelectedSignals), 1);

            % Get all signal data
            for i = 1:length(params.SelectedSignals)
                [timeData{i}, signalData{i}, sourceInfos{i}] = obj.getSignalData(params.SelectedSignals{i});
                if isempty(timeData{i})
                    error('Signal "%s" not found or empty.', params.SelectedSignals{i});
                end
            end

            % Align all signals
            [commonTime, alignedData] = obj.alignMultipleSignals(timeData, signalData, ...
                params.InterpolationMethod, params.TimeRange);

            % Compute norm
            switch params.NormType
                case 1  % L1 (Manhattan)
                    resultData = sum(abs(alignedData), 2);
                case 2  % L2 (Euclidean)
                    resultData = sqrt(sum(alignedData.^2, 2));
                case 3  % L∞ (Maximum)
                    resultData = max(abs(alignedData), [], 2);
            end

            % Create operation record
            operation = struct();
            operation.ID = obj.getNextOperationID();
            operation.Type = 'norm';
            operation.Operation = 'norm';
            operation.Timestamp = datetime('now');
            operation.InputSignals = params.SelectedSignals;
            operation.OutputSignal = params.ResultName;
            operation.Parameters = params;
            operation.SourceInfo = sourceInfos;

            % Store result
            obj.storeDerivedSignal(params.ResultName, commonTime, resultData, operation);

            % Update UI
            normTypes = {'L1', 'L2', 'L∞'};
            obj.App.StatusLabel.Text = sprintf('✅ Created %s norm: %s', normTypes{params.NormType}, params.ResultName);
            obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
        end

        %% =================================================================
        %% CUSTOM CODE OPERATIONS
        %% =================================================================
        %% =================================================================
        %% UTILITY METHODS
        %% =================================================================

        function signalNames = getAllAvailableSignals(obj)
            % Get all available signals (original + derived) from ALL CSVs
            signalNames = {};

            % Get signals from ALL CSV files
            for i = 1:numel(obj.App.DataManager.DataTables)
                T = obj.App.DataManager.DataTables{i};
                if ~isempty(T)
                    % Get signals from this CSV (excluding Time column)
                    csvSignals = setdiff(T.Properties.VariableNames, {'Time'});

                    % Add CSV index to signal names to make them unique
                    for j = 1:numel(csvSignals)
                        if numel(obj.App.DataManager.DataTables) > 1
                            % Multiple CSVs: add CSV identifier
                            [~, csvName, ~] = fileparts(obj.App.DataManager.CSVFilePaths{i});
                            uniqueSignalName = sprintf('%s (CSV%d: %s)', csvSignals{j}, i, csvName);
                        else
                            % Single CSV: use signal name as is
                            uniqueSignalName = csvSignals{j};
                        end
                        signalNames{end+1} = uniqueSignalName; %#ok<AGROW>
                    end
                end
            end

            % Add derived signals
            if ~isempty(obj.DerivedSignals)
                derivedNames = keys(obj.DerivedSignals);
                for i = 1:length(derivedNames)
                    signalNames{end+1} = sprintf('%s (Derived)', derivedNames{i}); %#ok<AGROW>
                end
            end

            % Fallback if no signals found
            if isempty(signalNames)
                signalNames = {'No signals available'};
            end
        end

        function [timeData, signalData, sourceInfo] = getSignalData(obj, signalName)
            % Initialize outputs
            timeData = [];
            signalData = [];
            sourceInfo = struct();

            % Input validation
            if isempty(signalName) || ~ischar(signalName)
                return;
            end

            % Clean signal name
            cleanSignalName = obj.extractCleanSignalName(signalName);

            % PRIORITY CHECK: Derived signals first
            if ~isempty(obj.DerivedSignals) && isKey(obj.DerivedSignals, cleanSignalName)
                derivedData = obj.DerivedSignals(cleanSignalName);
                timeData = derivedData.Time;
                signalData = derivedData.Data;
                sourceInfo.Type = 'derived';
                sourceInfo.Operation = derivedData.Operation;
                return;
            end

            % Handle original signals with bounds checking
            if contains(signalName, '(CSV')
                parts = split(signalName, ' (CSV');
                cleanSignalName = parts{1};

                csvPart = parts{2};
                csvIdxStr = regexp(csvPart, '(\d+)', 'tokens', 'once');
                if ~isempty(csvIdxStr)
                    csvIdx = str2double(csvIdxStr{1});

                    % BOUNDS CHECK: Ensure csvIdx is valid
                    if csvIdx > 0 && csvIdx <= numel(obj.App.DataManager.DataTables)
                        T = obj.App.DataManager.DataTables{csvIdx};
                        if ~isempty(T) && istable(T) && ismember(cleanSignalName, T.Properties.VariableNames)
                            timeData = T.Time;
                            signalData = T.(cleanSignalName);

                            % Remove NaN values
                            validIdx = ~isnan(signalData) & ~isnan(timeData);
                            timeData = timeData(validIdx);
                            signalData = signalData(validIdx);

                            sourceInfo.Type = 'original';
                            sourceInfo.CSVIndex = csvIdx;
                            if csvIdx <= numel(obj.App.DataManager.CSVFilePaths)
                                sourceInfo.CSVPath = obj.App.DataManager.CSVFilePaths{csvIdx};
                            end
                        end
                    end
                end
            else
                % Search all CSVs with bounds checking
                for i = 1:numel(obj.App.DataManager.DataTables)
                    T = obj.App.DataManager.DataTables{i};
                    if ~isempty(T) && istable(T) && ismember(cleanSignalName, T.Properties.VariableNames)
                        timeData = T.Time;
                        signalData = T.(cleanSignalName);

                        % Remove NaN values
                        validIdx = ~isnan(signalData) & ~isnan(timeData);
                        timeData = timeData(validIdx);
                        signalData = signalData(validIdx);

                        sourceInfo.Type = 'original';
                        sourceInfo.CSVIndex = i;
                        if i <= numel(obj.App.DataManager.CSVFilePaths)
                            sourceInfo.CSVPath = obj.App.DataManager.CSVFilePaths{i};
                        end
                        return;
                    end
                end
            end
        end
        function [commonTime, alignedA, alignedB] = alignTwoSignals(~, timeA, dataA, timeB, dataB, interpMethod, timeRangeOption)
            % Align two signals to a common time base

            % Determine time range
            switch timeRangeOption
                case 1  % Intersection (common)
                    minTime = max(min(timeA), min(timeB));
                    maxTime = min(max(timeA), max(timeB));
                case 2  % Union (all data)
                    minTime = min(min(timeA), min(timeB));
                    maxTime = max(max(timeA), max(timeB));
                case 3  % Signal A range
                    minTime = min(timeA);
                    maxTime = max(timeA);
                case 4  % Signal B range
                    minTime = min(timeB);
                    maxTime = max(timeB);
            end

            % Use finer resolution of the two signals
            dtA = mean(diff(timeA));
            dtB = mean(diff(timeB));
            dt = min(dtA, dtB) / 2;  % Use half the finer resolution for better accuracy

            % Create common time base
            commonTime = (minTime:dt:maxTime)';

            % Interpolate both signals
            alignedA = interp1(timeA, dataA, commonTime, interpMethod, 'extrap');
            alignedB = interp1(timeB, dataB, commonTime, interpMethod, 'extrap');

            % Remove any NaN or Inf values
            validIdx = isfinite(alignedA) & isfinite(alignedB);
            commonTime = commonTime(validIdx);
            alignedA = alignedA(validIdx);
            alignedB = alignedB(validIdx);
        end

        function [commonTime, alignedData] = alignMultipleSignals(~, timeData, signalData, interpMethod, timeRangeOption)
            % Align multiple signals to a common time base

            % Find time range
            allMinTimes = cellfun(@min, timeData);
            allMaxTimes = cellfun(@max, timeData);

            switch timeRangeOption
                case 1  % Intersection (common)
                    minTime = max(allMinTimes);
                    maxTime = min(allMaxTimes);
                case 2  % Union (all data)
                    minTime = min(allMinTimes);
                    maxTime = max(allMaxTimes);
            end

            % Find finest resolution
            allDts = cellfun(@(t) mean(diff(t)), timeData);
            dt = min(allDts) / 2;

            % Create common time base
            commonTime = (minTime:dt:maxTime)';

            % Interpolate all signals
            numSignals = length(signalData);
            alignedData = zeros(length(commonTime), numSignals);

            for i = 1:numSignals
                alignedData(:, i) = interp1(timeData{i}, signalData{i}, commonTime, interpMethod, 'extrap');
            end

            % Remove rows with any NaN or Inf values
            validIdx = all(isfinite(alignedData), 2);
            commonTime = commonTime(validIdx);
            alignedData = alignedData(validIdx, :);
        end


        function storeDerivedSignal(obj, signalName, timeData, signalData, operation)
            % Store a derived signal
            derivedSignal = struct();
            derivedSignal.Time = timeData(:);
            derivedSignal.Data = signalData(:);
            derivedSignal.Operation = operation;
            derivedSignal.CreatedAt = datetime('now');

            % Store in map
            obj.DerivedSignals(signalName) = derivedSignal;

            % Add to operation history
            obj.OperationHistory{end+1} = operation;

            % Limit history size
            if length(obj.OperationHistory) > obj.MaxHistorySize
                obj.OperationHistory(1) = [];
            end

            % Update signal names in DataManager
            if ~ismember(signalName, obj.App.DataManager.SignalNames)
                obj.App.DataManager.SignalNames{end+1} = signalName;
            end

            % Initialize signal properties
            obj.App.DataManager.SignalScaling(signalName) = 1.0;
            obj.App.DataManager.StateSignals(signalName) = false;

            % Rebuild signal tree to show new signal
            obj.App.buildSignalTree();
            obj.App.PlotManager.refreshPlots();
        end

        function id = getNextOperationID(obj)
            % Get next unique operation ID
            obj.OperationCounter = obj.OperationCounter + 1;
            id = sprintf('OP_%04d', obj.OperationCounter);
        end

        function deleteDerivedSignal(obj, signalName)
            % Delete a derived signal
            if obj.DerivedSignals.isKey(signalName)
                obj.DerivedSignals.remove(signalName);

                % Remove from DataManager signal names
                idx = strcmp(obj.App.DataManager.SignalNames, signalName);
                obj.App.DataManager.SignalNames(idx) = [];

                % Remove from signal maps
                if obj.App.DataManager.SignalScaling.isKey(signalName)
                    obj.App.DataManager.SignalScaling.remove(signalName);
                end
                if obj.App.DataManager.StateSignals.isKey(signalName)
                    obj.App.DataManager.StateSignals.remove(signalName);
                end

                % Rebuild signal tree
                obj.App.buildSignalTree();
                obj.App.PlotManager.refreshPlots();
            end
        end

        function clearAllDerivedSignals(obj)
            % Clear all derived signals
            derivedNames = keys(obj.DerivedSignals);
            for i = 1:length(derivedNames)
                obj.deleteDerivedSignal(derivedNames{i});
            end

            % Clear history
            obj.OperationHistory = {};
            obj.OperationCounter = 0;
        end

        function showOperationHistory(obj)
            % Show operation history dialog
            if isempty(obj.OperationHistory)
                uialert(obj.App.UIFigure, 'No operations in history.', 'Empty History');
                return;
            end

            % Create history dialog
            d = dialog('Name', 'Operation History', 'Position', [200 200 800 500], 'Resize', 'on');

            % Create table data
            numOps = length(obj.OperationHistory);
            tableData = cell(numOps, 6);

            for i = 1:numOps
                op = obj.OperationHistory{i};
                tableData{i, 1} = op.ID;
                tableData{i, 2} = char(op.Timestamp);
                tableData{i, 3} = op.Operation;
                tableData{i, 4} = strjoin(op.InputSignals, ', ');
                tableData{i, 5} = op.OutputSignal;
                tableData{i, 6} = op.Type;
            end

            % Create table
            historyTable = uitable('Parent', d, 'Position', [20 60 760 420], ...
                'Data', tableData, ...
                'ColumnName', {'ID', 'Timestamp', 'Operation', 'Input Signals', 'Output Signal', 'Type'}, ...
                'ColumnWidth', {60, 150, 100, 200, 150, 80}, ...
                'RowName', []);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Clear History', ...
                'Position', [20 20 100 30], 'Callback', @(~,~) clearHistory());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Export History', ...
                'Position', [130 20 100 30], 'Callback', @(~,~) exportHistory());
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [700 20 80 30], 'Callback', @(~,~) close(d));

            function clearHistory()
                answer = uiconfirm(d, 'Clear all operation history?', 'Confirm Clear', ...
                    'Options', {'Yes', 'No'}, 'DefaultOption', 'No');
                if strcmp(answer, 'Yes')
                    obj.OperationHistory = {};
                    close(d);
                end
            end

            function exportHistory()
                [file, path] = uiputfile('*.csv', 'Export Operation History');
                if ~isequal(file, 0)
                    try
                        T = table(tableData(:,1), tableData(:,2), tableData(:,3), ...
                            tableData(:,4), tableData(:,5), tableData(:,6), ...
                            'VariableNames', {'ID', 'Timestamp', 'Operation', ...
                            'InputSignals', 'OutputSignal', 'Type'});
                        writetable(T, fullfile(path, file));
                        uialert(d, 'History exported successfully!', 'Export Complete', 'Icon', 'success');
                    catch ME
                        uialert(d, sprintf('Export failed: %s', ME.message), 'Export Error');
                    end
                end
            end
        end

        %% =================================================================
        %% CONTEXT MENU INTEGRATION
        %% =================================================================

        function executeVectorMagnitude(obj, selectedSignals, resultName)
            % Execute vector magnitude calculation
            try
                % Get signal data
                timeData = cell(length(selectedSignals), 1);
                signalData = cell(length(selectedSignals), 1);

                for i = 1:length(selectedSignals)
                    [timeData{i}, signalData{i}] = obj.getSignalData(selectedSignals{i});
                    if isempty(timeData{i})
                        error('Signal "%s" not found or empty.', selectedSignals{i});
                    end
                end

                % Align signals to common time base
                [commonTime, alignedData] = obj.alignMultipleSignals(timeData, signalData, 'linear', 1);

                % Compute vector magnitude
                magnitude = sqrt(sum(alignedData.^2, 2));

                % Create operation record
                operation = struct();
                operation.ID = obj.getNextOperationID();
                operation.Type = 'quick_vector_magnitude';
                operation.Operation = 'vector_magnitude';
                operation.Timestamp = datetime('now');
                operation.InputSignals = selectedSignals;
                operation.OutputSignal = resultName;
                operation.Parameters = struct('SignalCount', length(selectedSignals));

                % Store result
                obj.storeDerivedSignal(resultName, commonTime, magnitude, operation);

                % Update UI
                obj.App.StatusLabel.Text = sprintf('✅ Created vector magnitude: %s', resultName);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ Vector magnitude failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        function executeMovingAverage(obj, signalName, windowSize, resultName)
            % Execute moving average calculation
            try
                % Get signal data
                [timeData, signalData] = obj.getSignalData(signalName);
                if isempty(timeData)
                    error('Signal "%s" not found or empty.', signalName);
                end

                % Apply moving average
                smoothedData = movmean(signalData, windowSize);

                % Create operation record
                operation = struct();
                operation.ID = obj.getNextOperationID();
                operation.Type = 'quick_moving_average';
                operation.Operation = 'moving_average';
                operation.Timestamp = datetime('now');
                operation.InputSignals = {signalName};
                operation.OutputSignal = resultName;
                operation.Parameters = struct('WindowSize', windowSize);

                % Store result
                obj.storeDerivedSignal(resultName, timeData, smoothedData, operation);

                % Update UI
                obj.App.StatusLabel.Text = sprintf('✅ Created moving average: %s', resultName);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ Moving average failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        function executeFFT(obj, signalName, outputType, resultName)
            % Execute FFT analysis
            try
                % Get signal data
                [timeData, signalData] = obj.getSignalData(signalName);
                if isempty(timeData)
                    error('Signal "%s" not found or empty.', signalName);
                end

                % Remove NaN values
                validIdx = isfinite(signalData);
                cleanSignal = signalData(validIdx);
                cleanTime = timeData(validIdx);

                if length(cleanSignal) < 4
                    error('Signal too short for FFT analysis.');
                end

                % Calculate sampling frequency
                dt = mean(diff(cleanTime));
                fs = 1/dt;

                % Apply windowing - FIXED VERSION
                N = length(cleanSignal);

                % Create Hanning window manually if hann() function is not available
                try
                    % Try to use the Signal Processing Toolbox function
                    window = hann(N);
                catch
                    % Create Hanning window manually
                    n = 0:N-1;
                    window = 0.5 * (1 - cos(2*pi*n/(N-1)))';
                    fprintf('Using manual Hanning window (Signal Processing Toolbox not available)\n');
                end

                windowedSignal = cleanSignal .* window;

                % Compute FFT
                Y = fft(windowedSignal);
                f = (0:floor(N/2)-1) * fs/N;

                % Generate output based on type
                switch outputType
                    case 1  % Magnitude
                        resultData = abs(Y(1:length(f)));
                    case 2  % Magnitude (dB)
                        resultData = 20*log10(abs(Y(1:length(f))) + eps);
                    case 3  % Phase
                        resultData = angle(Y(1:length(f))) * 180/pi;
                end

                % Create operation record
                operation = struct();
                operation.ID = obj.getNextOperationID();
                operation.Type = 'quick_fft';
                operation.Operation = 'fft_analysis';
                operation.Timestamp = datetime('now');
                operation.InputSignals = {signalName};
                operation.OutputSignal = resultName;
                operation.Parameters = struct('OutputType', outputType, 'SamplingFreq', fs);

                % Store result (frequency as time axis)
                obj.storeDerivedSignal(resultName, f, resultData, operation);

                % Update UI
                outputTypes = {'magnitude', 'magnitude (dB)', 'phase'};
                obj.App.StatusLabel.Text = sprintf('✅ Created FFT %s: %s', outputTypes{outputType}, resultName);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ FFT analysis failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        function executeRMS(obj, signalName, windowSize, resultName)
            % Execute windowed RMS calculation
            try
                % Get signal data
                [timeData, signalData] = obj.getSignalData(signalName);
                if isempty(timeData)
                    error('Signal "%s" not found or empty.', signalName);
                end

                % Calculate windowed RMS (vectorized for performance)
                % Ensure window size is an integer
                windowSize = round(windowSize);

                if windowSize > 1
                    % Use a backward-looking window to match the original loop's logic
                    rmsData = sqrt(movmean(signalData.^2, [windowSize-1 0]));
                else
                    rmsData = abs(signalData);
                end

                % Create operation record
                operation = struct();
                operation.ID = obj.getNextOperationID();
                operation.Type = 'quick_rms';
                operation.Operation = 'rms_windowed';
                operation.Timestamp = datetime('now');
                operation.InputSignals = {signalName};
                operation.OutputSignal = resultName;
                operation.Parameters = struct('WindowSize', windowSize);

                % Store result
                obj.storeDerivedSignal(resultName, timeData, rmsData, operation);

                % Update UI
                obj.App.StatusLabel.Text = sprintf('✅ Created windowed RMS: %s', resultName);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ RMS calculation failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        function executeSignalAverage(obj, selectedSignals, resultName)
            % Execute signal averaging
            try
                % Get signal data
                timeData = cell(length(selectedSignals), 1);
                signalData = cell(length(selectedSignals), 1);

                for i = 1:length(selectedSignals)
                    [timeData{i}, signalData{i}] = obj.getSignalData(selectedSignals{i});
                    if isempty(timeData{i})
                        error('Signal "%s" not found or empty.', selectedSignals{i});
                    end
                end

                % Align signals to common time base
                [commonTime, alignedData] = obj.alignMultipleSignals(timeData, signalData, 'linear', 1);

                % Compute average
                averageData = mean(alignedData, 2);

                % Create operation record
                operation = struct();
                operation.ID = obj.getNextOperationID();
                operation.Type = 'quick_average';
                operation.Operation = 'signal_average';
                operation.Timestamp = datetime('now');
                operation.InputSignals = selectedSignals;
                operation.OutputSignal = resultName;
                operation.Parameters = struct('SignalCount', length(selectedSignals));

                % Store result
                obj.storeDerivedSignal(resultName, commonTime, averageData, operation);

                % Update UI
                obj.App.StatusLabel.Text = sprintf('✅ Created signal average: %s', resultName);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ Signal averaging failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end


        function showQuickVectorMagnitude(obj)
            % Quick dialog for vector magnitude
            d = dialog('Name', 'Vector Magnitude', 'Position', [300 300 400 250], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 210 360 25], ...
                'String', 'Compute Vector Magnitude of Multiple Signals', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Select Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 100 360 75], 'String', signalNames, 'Max', length(signalNames));

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 70 230 25], 'String', 'vector_{magnitude}', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                selectedIndices = signalListbox.Value;
                if length(selectedIndices) < 2
                    msgbox('Please select at least 2 signals.', 'Invalid Selection', 'warn');
                    return;
                end

                resultName = strtrim(nameField.String);
                if isempty(resultName)
                    msgbox('Please enter a result name.', 'Invalid Input', 'warn');
                    return;
                end

                selectedSignals = signalNames(selectedIndices);
                obj.executeVectorMagnitude(selectedSignals, resultName);
                close(d);
            end
        end



        function showQuickMovingAverage(obj)
            % Quick dialog for moving average
            d = dialog('Name', 'Moving Average', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'Apply Moving Average to Signal', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames);

            % Window size
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Window Size:', 'FontWeight', 'bold');
            windowField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 100 25], 'String', '20', ...
                'HorizontalAlignment', 'left');

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', 'moving_{average}', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                windowSize = str2double(windowField.String);
                resultName = strtrim(nameField.String);

                if isnan(windowSize) || windowSize < 1
                    msgbox('Please enter a valid window size (>= 1).', 'Invalid Input', 'warn');
                    return;
                end

                if isempty(resultName)
                    msgbox('Please enter a result name.', 'Invalid Input', 'warn');
                    return;
                end

                obj.executeMovingAverage(signalName, windowSize, resultName);
                close(d);
            end
        end

        function showQuickFFT(obj)
            % Quick dialog for FFT analysis
            d = dialog('Name', 'FFT Analysis', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'FFT Magnitude Analysis', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames);

            % Output type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Output Type:', 'FontWeight', 'bold');
            typeDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 120 230 25], 'String', {'Magnitude', 'Magnitude (dB)', 'Phase'});

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', 'fft_{magnitude}', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                outputType = typeDropdown.Value;
                resultName = strtrim(nameField.String);

                if isempty(resultName)
                    msgbox('Please enter a result name.', 'Invalid Input', 'warn');
                    return;
                end

                obj.executeFFT(signalName, outputType, resultName);
                close(d);
            end
        end

        function showQuickRMS(obj)
            % Quick dialog for RMS calculation
            d = dialog('Name', 'RMS Calculation', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'Windowed RMS Calculation', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Select Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames);

            % Window size
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Window Size:', 'FontWeight', 'bold');
            windowField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 100 25], 'String', '100', ...
                'HorizontalAlignment', 'left');

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', 'rms_{windowed}', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                windowSize = str2double(windowField.String);
                resultName = strtrim(nameField.String);

                if isnan(windowSize) || windowSize < 1
                    msgbox('Please enter a valid window size (>= 1).', 'Invalid Input', 'warn');
                    return;
                end

                if isempty(resultName)
                    msgbox('Please enter a result name.', 'Invalid Input', 'warn');
                    return;
                end

                obj.executeRMS(signalName, windowSize, resultName);
                close(d);
            end
        end

        function showQuickAverage(obj)
            % Quick dialog for signal averaging
            d = dialog('Name', 'Signal Average', 'Position', [300 300 400 250], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 210 360 25], ...
                'String', 'Average Multiple Signals', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Select Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 100 360 75], 'String', signalNames, 'Max', length(signalNames));

            % Result name
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 70 230 25], 'String', 'signal_{average}', ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                selectedIndices = signalListbox.Value;
                if length(selectedIndices) < 2
                    msgbox('Please select at least 2 signals.', 'Invalid Selection', 'warn');
                    return;
                end

                resultName = strtrim(nameField.String);
                if isempty(resultName)
                    msgbox('Please enter a result name.', 'Invalid Input', 'warn');
                    return;
                end

                selectedSignals = signalNames(selectedIndices);
                obj.executeSignalAverage(selectedSignals, resultName);
                close(d);
            end
        end

        function showOperationDetails(~, operation)
            % Show detailed information about an operation
            d = dialog('Name', 'Operation Details', 'Position', [300 300 500 400], 'Resize', 'on');

            % Create text display
            detailsText = uicontrol('Parent', d, 'Style', 'edit', 'Position', [20 60 460 320], ...
                'Max', 20, 'HorizontalAlignment', 'left', 'FontName', 'Courier New', ...
                'FontSize', 10, 'Enable', 'off');

            % Format operation details
            details = {
                sprintf('Operation ID: %s', operation.ID)
                sprintf('Type: %s', operation.Type)
                sprintf('Operation: %s', operation.Operation)
                sprintf('Timestamp: %s', char(operation.Timestamp))
                sprintf('Input Signals: %s', strjoin(operation.InputSignals, ', '))
                sprintf('Output Signal: %s', operation.OutputSignal)
                ''
                'Parameters:'
                };

            % Add parameters
            if isstruct(operation.Parameters)
                paramFields = fieldnames(operation.Parameters);
                for i = 1:length(paramFields)
                    field = paramFields{i};
                    value = operation.Parameters.(field);
                    if ischar(value) || isstring(value)
                        details{end+1} = sprintf('  %s: %s', field, value);
                    elseif isnumeric(value) && isscalar(value)
                        details{end+1} = sprintf('  %s: %.6g', field, value);
                    elseif iscell(value)
                        details{end+1} = sprintf('  %s: {%s}', field, strjoin(cellfun(@char, value, 'UniformOutput', false), ', '));
                    else
                        details{end+1} = sprintf('  %s: [%s]', field, class(value));
                    end
                end
            end

            detailsText.String = details;

            % Close button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Close', ...
                'Position', [400 20 80 30], 'Callback', @(~,~) close(d));
        end

        function updateDerivedSignalsAfterStream(obj, csvIdx)
            % Update derived signals automatically after new streaming data arrives
            % csvIdx - index of the CSV file that was just updated

            if ~isprop(obj.App, 'SignalOperations') || isempty(obj.App.SignalOperations)
                return;
            end

            signalOps = obj.App.SignalOperations;

            % Check if there are any derived signals to update
            if isempty(signalOps.DerivedSignals)
                return;
            end

            try
                % Get list of signals that were just updated in the specific CSV
                updatedOriginalSignals = obj.getRecentlyUpdatedSignals(csvIdx);
                if isempty(updatedOriginalSignals)
                    return;
                end

                % Find derived signals that depend on the updated original signals
                derivedSignalsToUpdate = {};
                derivedNames = keys(signalOps.DerivedSignals);

                for i = 1:length(derivedNames)
                    derivedName = derivedNames{i};
                    derivedData = signalOps.DerivedSignals(derivedName);

                    % Check if this derived signal depends on any updated original signals
                    inputSignals = derivedData.Operation.InputSignals;

                    % Check for dependency
                    hasUpdatedDependency = false;
                    for j = 1:length(inputSignals)
                        if ismember(inputSignals{j}, updatedOriginalSignals)
                            hasUpdatedDependency = true;
                            break;
                        end
                    end

                    if hasUpdatedDependency
                        derivedSignalsToUpdate{end+1} = derivedName; %#ok<AGROW>
                    end
                end

                % Update each dependent derived signal
                updatedCount = 0;
                for i = 1:length(derivedSignalsToUpdate)
                    derivedName = derivedSignalsToUpdate{i};
                    success = obj.recalculateDerivedSignal(signalOps, derivedName);
                    if success
                        updatedCount = updatedCount + 1;
                    end
                end

                % Update plots if any derived signals were recalculated
                if updatedCount > 0
                    obj.App.PlotManager.refreshPlots();

                    % Update status
                    obj.App.StatusLabel.Text = sprintf('🔄 Updated %d derived signal(s) from CSV %d', updatedCount, csvIdx);
                    obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
                end

            catch ME
                % Log error but don't interrupt streaming
                fprintf('Warning: Failed to update derived signals for CSV %d: %s\n', csvIdx, ME.message);
                obj.App.StatusLabel.Text = sprintf('⚠️ Derived signal update failed for CSV %d', csvIdx);
                obj.App.StatusLabel.FontColor = [0.9 0.6 0.2];
            end
        end

        function updatedSignals = getRecentlyUpdatedSignals(obj, csvIdx)
            % Get list of signals that were actually updated in the specified CSV
            % csvIdx - the index of the CSV that was just updated

            updatedSignals = {};

            if nargin < 2 || csvIdx <= 0 || csvIdx > numel(obj.DataTables)
                return;
            end

            % Get signals from the specific CSV that was updated
            if ~isempty(obj.DataTables{csvIdx})
                signals = setdiff(obj.DataTables{csvIdx}.Properties.VariableNames, {'Time'});
                updatedSignals = signals;
            end

            % Track last update times for more precise tracking
            currentTime = datetime('now');

            % Initialize LastSignalUpdateTimes if it doesn't exist
            if ~isprop(obj, 'LastSignalUpdateTimes') || isempty(obj.LastSignalUpdateTimes)
                obj.LastSignalUpdateTimes = containers.Map('KeyType', 'char', 'ValueType', 'any');
            end

            % Update timestamps for all signals in this CSV
            for i = 1:length(updatedSignals)
                signalName = updatedSignals{i};
                obj.LastSignalUpdateTimes(signalName) = currentTime;
            end
        end

        % UPDATE the recalculateDerivedSignal method in SignalOperationsManager to handle new operation types:

        function success = recalculateDerivedSignal(obj, signalOps, derivedName)
            % Recalculate a specific derived signal based on its operation

            success = false;

            if ~signalOps.DerivedSignals.isKey(derivedName)
                return;
            end

            derivedData = signalOps.DerivedSignals(derivedName);
            operation = derivedData.Operation;

            try
                % Check if all input signals still exist and get fresh data
                inputSignals = operation.InputSignals;
                signalDataExists = true;

                for i = 1:length(inputSignals)
                    [timeData, ~] = signalOps.getSignalData(inputSignals{i});
                    if isempty(timeData)
                        signalDataExists = false;
                        fprintf('Warning: Input signal "%s" no longer exists for derived signal "%s"\n', ...
                            inputSignals{i}, derivedName);
                        break;
                    end
                end

                if ~signalDataExists
                    return;
                end

                % Recreate the derived signal based on its operation type
                switch operation.Type
                    case 'single'
                        success = obj.recalculateSingleSignalOperation(signalOps, operation);

                    case 'dual'
                        success = obj.recalculateDualSignalOperation(signalOps, operation);

                    case 'norm'
                        success = obj.recalculateNormOperation(signalOps, operation);

                    case {'quick_vector_magnitude', 'quick_average'}
                        success = obj.recalculateQuickMultiSignalOperation(signalOps, operation);

                    case {'quick_moving_average', 'quick_fft', 'quick_rms'}
                        success = obj.recalculateQuickSingleSignalOperation(signalOps, operation);

                    otherwise
                        warning('Unknown operation type: %s', operation.Type);
                end

            catch ME
                fprintf('Warning: Failed to recalculate derived signal "%s": %s\n', derivedName, ME.message);
                success = false;
            end
        end

        % ADD these new recalculation methods:

        function success = recalculateQuickSingleSignalOperation(~, signalOps, operation)
            % Recalculate quick single signal operations

            success = false;
            inputSignal = operation.InputSignals{1};
            [timeData, signalData] = signalOps.getSignalData(inputSignal);

            if isempty(timeData)
                return;
            end

            try
                switch operation.Type
                    case 'quick_moving_average'
                        windowSize = operation.Parameters.WindowSize;
                        resultData = movmean(signalData, windowSize);
                        resultTime = timeData;

                    case 'quick_rms'
                        windowSize = operation.Parameters.WindowSize;
                        windowSize = round(windowSize);
                        if windowSize > 1
                            rmsData = sqrt(movmean(signalData.^2, [windowSize-1 0]));
                        else
                            rmsData = abs(signalData);
                        end
                        resultData = rmsData;
                        resultTime = timeData;

                    case 'quick_fft'
                        % Recalculate FFT
                        validIdx = isfinite(signalData);
                        cleanSignal = signalData(validIdx);
                        cleanTime = timeData(validIdx);

                        if length(cleanSignal) < 4
                            return;
                        end

                        dt = mean(diff(cleanTime));
                        fs = 1/dt;
                        N = length(cleanSignal);

                        % Create Hanning window manually if hann() function is not available
                        try
                            % Try to use the Signal Processing Toolbox function
                            window = hann(N);
                        catch
                            % Create Hanning window manually
                            n = 0:N-1;
                            window = 0.5 * (1 - cos(2*pi*n/(N-1)))';
                        end

                        windowedSignal = cleanSignal .* window;
                        Y = fft(windowedSignal);
                        f = (0:floor(N/2)-1) * fs/N;

                        outputType = operation.Parameters.OutputType;
                        switch outputType
                            case 1  % Magnitude
                                resultData = abs(Y(1:length(f)));
                            case 2  % Magnitude (dB)
                                resultData = 20*log10(abs(Y(1:length(f))) + eps);
                            case 3  % Phase
                                resultData = angle(Y(1:length(f))) * 180/pi;
                        end
                        resultTime = f;

                    otherwise
                        return;
                end

                % Update the derived signal
                existingDerived = signalOps.DerivedSignals(operation.OutputSignal);
                derivedSignal = struct();
                derivedSignal.Time = resultTime;
                derivedSignal.Data = resultData;
                derivedSignal.Operation = operation;
                derivedSignal.CreatedAt = existingDerived.CreatedAt;
                derivedSignal.UpdatedAt = datetime('now');

                signalOps.DerivedSignals(operation.OutputSignal) = derivedSignal;
                success = true;

            catch ME
                fprintf('Warning: Failed to recalculate quick single signal operation: %s\n', ME.message);
            end
        end

        function success = recalculateQuickMultiSignalOperation(~, signalOps, operation)
            % Recalculate quick multi signal operations

            success = false;
            signalData = cell(length(operation.InputSignals), 1);
            timeData = cell(length(operation.InputSignals), 1);

            % Get all signal data
            for i = 1:length(operation.InputSignals)
                [timeData{i}, signalData{i}] = signalOps.getSignalData(operation.InputSignals{i});
                if isempty(timeData{i})
                    return;
                end
            end

            try
                % Align signals
                [commonTime, alignedData] = signalOps.alignMultipleSignals(timeData, signalData, 'linear', 1);

                switch operation.Type
                    case 'quick_vector_magnitude'
                        resultData = sqrt(sum(alignedData.^2, 2));

                    case 'quick_average'
                        resultData = mean(alignedData, 2);

                    otherwise
                        return;
                end

                % Update the derived signal
                existingDerived = signalOps.DerivedSignals(operation.OutputSignal);
                derivedSignal = struct();
                derivedSignal.Time = commonTime;
                derivedSignal.Data = resultData;
                derivedSignal.Operation = operation;
                derivedSignal.CreatedAt = existingDerived.CreatedAt;
                derivedSignal.UpdatedAt = datetime('now');

                signalOps.DerivedSignals(operation.OutputSignal) = derivedSignal;
                success = true;

            catch ME
                fprintf('Warning: Failed to recalculate quick multi signal operation: %s\n', ME.message);
            end
        end
        function success = recalculateSingleSignalOperation(~, signalOps, operation)
            % Recalculate single signal operations (derivative, integral)

            success = false;

            inputSignal = operation.InputSignals{1};
            [timeData, signalData, ~] = signalOps.getSignalData(inputSignal);

            if isempty(timeData)
                return; % Signal no longer exists
            end

            try
                % Perform the operation using the same parameters
                switch operation.Operation
                    case 'derivative'
                        result = signalOps.computeDerivative(timeData, signalData, operation.Parameters);
                    case 'integral'
                        result = signalOps.computeIntegral(timeData, signalData, operation.Parameters);
                    otherwise
                        return;
                end

                % Get the existing derived signal to preserve metadata
                existingDerived = signalOps.DerivedSignals(operation.OutputSignal);

                % Update the derived signal
                derivedSignal = struct();
                derivedSignal.Time = result.Time;
                derivedSignal.Data = result.Data;
                derivedSignal.Operation = operation;
                derivedSignal.CreatedAt = existingDerived.CreatedAt; % Keep original creation time
                derivedSignal.UpdatedAt = datetime('now'); % Add update time

                signalOps.DerivedSignals(operation.OutputSignal) = derivedSignal;
                success = true;

            catch ME
                fprintf('Warning: Failed to recalculate single signal operation: %s\n', ME.message);
            end
        end


        function addDerivedSignalsToTree(obj)
            % Add only derived signals to the tree (not operations)
            if isempty(obj.DerivedSignals)
                return;
            end

            % Get current subplot assignments for visual indicators
            tabIdx = obj.App.PlotManager.CurrentTabIdx;
            subplotIdx = obj.App.PlotManager.SelectedSubplotIdx;
            assignedSignals = {};
            if tabIdx <= numel(obj.App.PlotManager.AssignedSignals) && subplotIdx <= numel(obj.App.PlotManager.AssignedSignals{tabIdx})
                assignedSignals = obj.App.PlotManager.AssignedSignals{tabIdx}{subplotIdx};
            end

            derivedNode = uitreenode(obj.App.SignalTree, 'Text', '⚙️ Derived Signals', ...
                'NodeData', struct('Type', 'derived_signals_folder'));

            derivedNames = keys(obj.DerivedSignals);
            for i = 1:length(derivedNames)
                signalName = derivedNames{i};
                derivedData = obj.DerivedSignals(signalName);

                % Create icon based on operation type
                switch derivedData.Operation.Type
                    case 'single'
                        if strcmp(derivedData.Operation.Operation, 'derivative')
                            icon = '∂';
                        else
                            icon = '∫';
                        end
                    case 'dual'
                        opIcons = containers.Map({'subtract', 'add', 'multiply', 'divide'}, {'−', '+', '×', '÷'});
                        if isKey(opIcons, derivedData.Operation.Operation)
                            icon = opIcons(derivedData.Operation.Operation);
                        else
                            icon = '⚙️';
                        end
                    case 'norm'
                        icon = '‖‖';
                    case {'quick_vector_magnitude', 'quick_moving_average', 'quick_fft', 'quick_rms', 'quick_average'}
                        icon = '⚡';
                    otherwise
                        icon = '🔄';
                end

                child = uitreenode(derivedNode, 'Text', sprintf('%s %s', icon, signalName));
                child.NodeData = struct('CSVIdx', -1, 'Signal', signalName, 'IsDerived', true);

                % ============= ADD CONTEXT MENU FOR EACH DERIVED SIGNAL NODE =============
                % Add context menu for derived signals - INDIVIDUAL NODE MENU
                derivedSignalContextMenu = uicontextmenu(obj.App.UIFigure);

                % Check if this derived signal is assigned to current subplot
                signalInfo = struct('CSVIdx', -1, 'Signal', signalName);
                isAssigned = false;
                for k = 1:numel(assignedSignals)
                    if isequal(assignedSignals{k}, signalInfo)
                        isAssigned = true;
                        break;
                    end
                end

                % Add appropriate menu items
                if isAssigned
                    uimenu(derivedSignalContextMenu, 'Text', '❌ Remove from Subplot', ...
                        'MenuSelectedFcn', @(src, event) obj.App.removeSignalFromCurrentSubplot(signalInfo));
                else
                    uimenu(derivedSignalContextMenu, 'Text', '➕ Add to Subplot', ...
                        'MenuSelectedFcn', @(src, event) obj.App.addSignalToCurrentSubplot(signalInfo));
                end

                uimenu(derivedSignalContextMenu, 'Text', '📊 Quick Preview', ...
                    'MenuSelectedFcn', @(src, event) obj.App.showSignalPreview(signalInfo), ...
                    'Separator', 'on');

                uimenu(derivedSignalContextMenu, 'Text', '🗑️ Delete Signal', ...
                    'MenuSelectedFcn', @(src, event) obj.confirmDeleteDerivedSignal(signalName));

                uimenu(derivedSignalContextMenu, 'Text', '📋 Show Details', ...
                    'MenuSelectedFcn', @(src, event) obj.showOperationDetails(derivedData.Operation));

                uimenu(derivedSignalContextMenu, 'Text', '💾 Export Signal', ...
                    'MenuSelectedFcn', @(src, event) obj.exportDerivedSignal(signalName));

                % Assign context menu to the derived signal node
                child.ContextMenu = derivedSignalContextMenu;
                % ============= END CONTEXT MENU ADDITION =============
            end

            % SIMPLE FIX: Always expand derived signals and add to expanded list
            if ~isprop(obj.App, 'ExpandedTreeNodes')
                obj.App.ExpandedTreeNodes = string.empty;
            end

            derivedNodeText = '⚙️ Derived Signals';

            % Add to expanded nodes list if not already there
            if ~any(strcmp(derivedNodeText, obj.App.ExpandedTreeNodes))
                obj.App.ExpandedTreeNodes(end+1) = derivedNodeText;
            end

            % Force expansion immediately
            try
                derivedNode.expand();
                fprintf('Auto-expanded derived signals node\n');
            catch
                try
                    derivedNode.Expanded = true;
                    fprintf('Set derived signals node Expanded=true\n');
                catch
                    fprintf('Could not expand derived signals node\n');
                end
            end

            % Debug output
            fprintf('Added %d derived signals to tree (auto-expanded)\n', length(derivedNames));
        end

        % Add these methods to SignalOperationsManager.m

        function showSingleSignalDialogWithPreselection(obj, operationType, preselectedSignal)
            % Create dialog for single signal operations with pre-selected signal
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 450 300], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 410 25], ...
                'String', sprintf('Compute %s of Signal', operationType), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();

            % Find the index of the pre-selected signal
            preselectedIndex = 1;
            for i = 1:length(signalNames)
                if strcmp(signalNames{i}, preselectedSignal)
                    preselectedIndex = i;
                    break;
                end
            end

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 220 250 25], 'String', signalNames, 'Value', preselectedIndex);

            % Method selection (operation-specific)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Method:', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'derivative'
                    methods = {'Gradient (recommended)', 'Forward Difference', 'Backward Difference', 'Central Difference'};
                    defaultMethod = 1;
                case 'integral'
                    methods = {'Cumulative Trapezoidal', 'Cumulative Simpson', 'Running Sum'};
                    defaultMethod = 1;
                otherwise
                    methods = {'Default'};
                    defaultMethod = 1;
            end

            methodDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 180 250 25], 'String', methods, 'Value', defaultMethod);

            % Result name - AUTO-GENERATED based on selected signal
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 140 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            % Extract clean signal name for result
            cleanSignalName = obj.extractCleanSignalName(preselectedSignal);
            defaultName = sprintf('%s_%s', cleanSignalName, lower(operationType));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 140 250 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Update name when signal changes
            signalDropdown.Callback = @(src, ~) updateDefaultName();

            % Options (operation-specific)
            optionsPanel = uipanel('Parent', d, 'Position', [20 60 410 70], ...
                'Title', 'Options', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'derivative'
                    smoothingCheck = uicontrol('Parent', optionsPanel, 'Style', 'checkbox', ...
                        'Position', [10 30 200 20], 'String', 'Apply smoothing filter', 'Value', 0);
                    windowSizeLabel = uicontrol('Parent', optionsPanel, 'Style', 'text', ...
                        'Position', [10 5 100 20], 'String', 'Window size:');
                    windowSizeEdit = uicontrol('Parent', optionsPanel, 'Style', 'edit', ...
                        'Position', [120 5 50 20], 'String', '5', 'Enable', 'off');

                    smoothingCheck.Callback = @(src, ~) set(windowSizeEdit, 'Enable', ...
                        char("on" * src.Value + "off" * (1-src.Value)));

                case 'integral'
                    initialValueCheck = uicontrol('Parent', optionsPanel, 'Style', 'checkbox', ...
                        'Position', [10 30 200 20], 'String', 'Set initial value', 'Value', 0);
                    initialValueLabel = uicontrol('Parent', optionsPanel, 'Style', 'text', ...
                        'Position', [10 5 100 20], 'String', 'Initial value:');
                    initialValueEdit = uicontrol('Parent', optionsPanel, 'Style', 'edit', ...
                        'Position', [120 5 50 20], 'String', '0', 'Enable', 'off');

                    initialValueCheck.Callback = @(src, ~) set(initialValueEdit, 'Enable', ...
                        char("on" * src.Value + "off" * (1-src.Value)));
            end

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [250 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [340 15 80 30], 'Callback', @(~,~) close(d));

            function updateDefaultName()
                selectedSignal = signalNames{signalDropdown.Value};
                cleanName = obj.extractCleanSignalName(selectedSignal);
                newName = sprintf('%s_%s', cleanName, lower(operationType));
                nameField.String = newName;
            end

            function computeAndClose()
                params = struct();
                params.SignalName = signalNames{signalDropdown.Value};
                params.Method = methods{methodDropdown.Value};
                params.ResultName = strtrim(nameField.String);

                % Add operation-specific parameters
                switch lower(operationType)
                    case 'derivative'
                        params.ApplySmoothing = smoothingCheck.Value;
                        if params.ApplySmoothing
                            params.WindowSize = str2double(windowSizeEdit.String);
                        end
                    case 'integral'
                        params.SetInitialValue = initialValueCheck.Value;
                        if params.SetInitialValue
                            params.InitialValue = str2double(initialValueEdit.String);
                        end
                end

                % Validate inputs
                if isempty(params.ResultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                % Execute operation
                obj.executeSingleSignalOperation(operationType, params);
                close(d);
            end
        end

        function showDualSignalDialogWithPreselection(obj, operationType, preselectedSignalA, preselectedSignalB)
            % Dialog for two-signal operations with pre-selected signals
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 500 350], 'Resize', 'off');

            % Title
            opSymbols = containers.Map({'subtract', 'add', 'multiply', 'divide'}, ...
                {'−', '+', '×', '÷'});
            opSymbol = opSymbols(lower(operationType));

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 310 460 25], ...
                'String', sprintf('Signal A %s Signal B', opSymbol), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            signalNames = obj.getAllAvailableSignals();

            % Find indices of pre-selected signals
            indexA = 1;
            indexB = min(2, length(signalNames));

            for i = 1:length(signalNames)
                if strcmp(signalNames{i}, preselectedSignalA)
                    indexA = i;
                end
                if strcmp(signalNames{i}, preselectedSignalB)
                    indexB = i;
                end
            end

            % Signal A selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 270 120 20], ...
                'String', 'Signal A:', 'FontWeight', 'bold');
            signalADropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 270 250 25], 'String', signalNames, 'Value', indexA);

            % Signal B selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 120 20], ...
                'String', 'Signal B:', 'FontWeight', 'bold');
            signalBDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 230 250 25], 'String', signalNames, 'Value', indexB);

            % Interpolation options
            interpPanel = uipanel('Parent', d, 'Position', [20 140 460 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)', 'Signal A range', 'Signal B range'}, ...
                'Value', 1);

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            % Generate default name from pre-selected signals
            cleanNameA = obj.extractCleanSignalName(preselectedSignalA);
            cleanNameB = obj.extractCleanSignalName(preselectedSignalB);
            defaultName = sprintf('%s_%s_%s', cleanNameA, lower(operationType), cleanNameB);
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 100 250 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Update name when signals change
            updateName = @(~,~) set(nameField, 'String', sprintf('%s_%s_%s', ...
                obj.extractCleanSignalName(signalNames{signalADropdown.Value}), lower(operationType), ...
                obj.extractCleanSignalName(signalNames{signalBDropdown.Value})));
            signalADropdown.Callback = updateName;
            signalBDropdown.Callback = updateName;

            % Preview button
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Preview', ...
                'Position', [150 50 80 30], 'Callback', @(~,~) showPreview());

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [320 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [410 15 80 30], 'Callback', @(~,~) close(d));

            function showPreview()
                % Show preview implementation (same as original)
                try
                    signalA = signalNames{signalADropdown.Value};
                    signalB = signalNames{signalBDropdown.Value};

                    [timeA, dataA] = obj.getSignalData(signalA);
                    [timeB, dataB] = obj.getSignalData(signalB);

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    interpMethod = interpMethods{interpDropdown.Value};

                    [commonTime, alignedA, alignedB] = obj.alignTwoSignals(timeA, dataA, timeB, dataB, ...
                        interpMethod, rangeDropdown.Value);

                    % Create preview figure
                    fig = figure('Name', 'Signal Alignment Preview', 'Position', [100 100 800 600]);

                    subplot(3,1,1);
                    plot(timeA, dataA, 'b-', 'LineWidth', 1.5); hold on;
                    plot(timeB, dataB, 'r-', 'LineWidth', 1.5);
                    legend({signalA, signalB}, 'Location', 'best');
                    title('Original Signals');
                    grid on;

                    subplot(3,1,2);
                    plot(commonTime, alignedA, 'b-', 'LineWidth', 1.5); hold on;
                    plot(commonTime, alignedB, 'r-', 'LineWidth', 1.5);
                    legend({[signalA ' (aligned)'], [signalB ' (aligned)']}, 'Location', 'best');
                    title('Aligned Signals');
                    grid on;

                    subplot(3,1,3);
                    switch lower(operationType)
                        case 'subtract'
                            resultData = alignedA - alignedB;
                            opStr = sprintf('%s - %s', signalA, signalB);
                        case 'add'
                            resultData = alignedA + alignedB;
                            opStr = sprintf('%s + %s', signalA, signalB);
                        case 'multiply'
                            resultData = alignedA .* alignedB;
                            opStr = sprintf('%s × %s', signalA, signalB);
                        case 'divide'
                            resultData = alignedA ./ alignedB;
                            opStr = sprintf('%s ÷ %s', signalA, signalB);
                    end
                    plot(commonTime, resultData, 'g-', 'LineWidth', 2);
                    title(sprintf('Result: %s', opStr));
                    grid on;

                catch ME
                    uialert(d, sprintf('Preview error: %s', ME.message), 'Preview Failed');
                end
            end

            function computeAndClose()
                try
                    params = struct();
                    params.SignalA = signalNames{signalADropdown.Value};
                    params.SignalB = signalNames{signalBDropdown.Value};
                    params.ResultName = strtrim(nameField.String);

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    params.InterpolationMethod = interpMethods{interpDropdown.Value};
                    params.TimeRange = rangeDropdown.Value;

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    if strcmp(params.SignalA, params.SignalB)
                        uialert(d, 'Please select different signals for A and B.', 'Invalid Input');
                        return;
                    end

                    % Execute operation
                    obj.executeDualSignalOperation(operationType, params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function showQuickMovingAverageWithPreselection(obj, preselectedSignal)
            % Quick dialog for moving average with pre-selected signal
            d = dialog('Name', 'Moving Average', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'Apply Moving Average to Signal', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            preselectedIndex = 1;
            for i = 1:length(signalNames)
                if strcmp(signalNames{i}, preselectedSignal)
                    preselectedIndex = i;
                    break;
                end
            end

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames, 'Value', preselectedIndex);

            % Window size
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Window Size:', 'FontWeight', 'bold');
            windowField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 100 25], 'String', '100', ...
                'HorizontalAlignment', 'left');

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanSignalName = obj.extractCleanSignalName(preselectedSignal);
            defaultName = sprintf('%s_rms', cleanSignalName);
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                windowSize = str2double(windowField.String);
                resultName = strtrim(nameField.String);

                if isnan(windowSize) || windowSize < 1
                    uialert(d, 'Please enter a valid window size (>= 1).', 'Invalid Input');
                    return;
                end

                if isempty(resultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                obj.executeRMS(signalName, windowSize, resultName);
                close(d);
            end
        end

        function showQuickVectorMagnitudeWithPreselection(obj, preselectedSignals)
            % Quick dialog for vector magnitude with pre-selected signals
            d = dialog('Name', 'Vector Magnitude', 'Position', [300 300 400 300], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 360 25], ...
                'String', 'Compute Vector Magnitude of Multiple Signals', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 120 20], ...
                'String', 'Selected Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();

            % Find indices of pre-selected signals
            preselectedIndices = [];
            for i = 1:length(preselectedSignals)
                for j = 1:length(signalNames)
                    if strcmp(signalNames{j}, preselectedSignals{i})
                        preselectedIndices(end+1) = j;
                        break;
                    end
                end
            end

            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 150 360 75], 'String', signalNames, 'Max', length(signalNames), ...
                'Value', preselectedIndices);

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            defaultName = sprintf('vector_magnitude_%d_signals', length(preselectedSignals));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Show selected count
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 360 20], ...
                'String', sprintf('%d signals pre-selected for vector magnitude calculation', length(preselectedSignals)), ...
                'FontSize', 9, 'ForegroundColor', [0.2 0.6 0.9]);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                selectedIndices = signalListbox.Value;
                if length(selectedIndices) < 2
                    uialert(d, 'Please select at least 2 signals.', 'Invalid Selection');
                    return;
                end

                resultName = strtrim(nameField.String);
                if isempty(resultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                selectedSignals = signalNames(selectedIndices);
                obj.executeVectorMagnitude(selectedSignals, resultName);
                close(d);
            end
        end

        function showSimplifiedDualSignalDialog(obj, operationType, signal1Name, signal2Name)
            % Simplified dialog for dual signal operations with fixed signal selection
            opSymbols = containers.Map({'add', 'subtract', 'multiply', 'divide'}, ...
                {'+', '−', '×', '÷'});
            opSymbol = opSymbols(lower(operationType));

            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 450 300], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 410 25], ...
                'String', sprintf('Signal A %s Signal B', opSymbol), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Show selected signals (read-only)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 80 20], ...
                'String', 'Signal A:', 'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'text', 'Position', [110 220 320 20], ...
                'String', signal1Name, 'FontWeight', 'normal', ...
                'BackgroundColor', [0.9 0.9 0.9], 'HorizontalAlignment', 'left');

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 190 80 20], ...
                'String', 'Signal B:', 'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'text', 'Position', [110 190 320 20], ...
                'String', signal2Name, 'FontWeight', 'normal', ...
                'BackgroundColor', [0.9 0.9 0.9], 'HorizontalAlignment', 'left');

            % Interpolation options
            interpPanel = uipanel('Parent', d, 'Position', [20 100 410 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)', 'Signal A range', 'Signal B range'}, ...
                'Value', 1);

            % Result name - auto-generated
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanNameA = obj.extractCleanSignalName(signal1Name);
            cleanNameB = obj.extractCleanSignalName(signal2Name);
            defaultName = sprintf('%s_%s_%s', cleanNameA, lower(operationType), cleanNameB);
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 70 280 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [270 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [360 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    params = struct();
                    params.SignalA = signal1Name;
                    params.SignalB = signal2Name;
                    params.ResultName = strtrim(nameField.String);

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    params.InterpolationMethod = interpMethods{interpDropdown.Value};
                    params.TimeRange = rangeDropdown.Value;

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    % Execute operation
                    obj.executeDualSignalOperation(operationType, params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function showSimplifiedMultiSignalDialog(obj, operationType, selectedSignalNames)
            % Simplified dialog for multi-signal operations with fixed signal selection
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 500 400], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 460 25], ...
                'String', sprintf('%s of Selected Signals', operationType), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Show selected signals (read-only list)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 330 150 20], ...
                'String', 'Selected Signals:', 'FontWeight', 'bold');

            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 250 460 75], 'String', selectedSignalNames, 'Enable', 'off');

            % Operation-specific options
            switch lower(operationType)
                case 'norm'
                    % Norm type
                    uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                        'String', 'Norm Type:', 'FontWeight', 'bold');
                    normDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                        'Position', [150 220 150 25], ...
                        'String', {'L1 (Manhattan)', 'L2 (Euclidean)', 'L∞ (Maximum)'}, 'Value', 2);
            end

            % Interpolation options (for all multi-signal operations)
            interpPanel = uipanel('Parent', d, 'Position', [20 120 460 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)'}, 'Value', 1);

            % Result name - auto-generated
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 80 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'vector magnitude'
                    defaultName = sprintf('vector_magnitude_%d_signals', length(selectedSignalNames));
                case 'signal average'
                    defaultName = sprintf('signal_average_%d_signals', length(selectedSignalNames));
                case 'norm'
                    defaultName = sprintf('norm_%d_signals', length(selectedSignalNames));
            end

            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 80 330 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [320 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [410 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    resultName = strtrim(nameField.String);
                    if isempty(resultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    switch lower(operationType)
                        case 'vector magnitude'
                            obj.executeVectorMagnitude(selectedSignalNames, resultName);
                        case 'signal average'
                            obj.executeSignalAverage(selectedSignalNames, resultName);
                        case 'norm'
                            params = struct();
                            params.SelectedSignals = selectedSignalNames;
                            params.ResultName = resultName;
                            params.NormType = normDropdown.Value;

                            interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                            params.InterpolationMethod = interpMethods{interpDropdown.Value};
                            params.TimeRange = rangeDropdown.Value;

                            obj.executeNormOperation(params);
                    end

                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function showQuickAverageWithPreselection(obj, preselectedSignals)
            % Quick dialog for signal averaging with pre-selected signals
            d = dialog('Name', 'Signal Average', 'Position', [300 300 400 300], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 260 360 25], ...
                'String', 'Average Multiple Signals', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 230 120 20], ...
                'String', 'Selected Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();

            % Find indices of pre-selected signals
            preselectedIndices = [];
            for i = 1:length(preselectedSignals)
                for j = 1:length(signalNames)
                    if strcmp(signalNames{j}, preselectedSignals{i})
                        preselectedIndices(end+1) = j;
                        break;
                    end
                end
            end

            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [20 150 360 75], 'String', signalNames, 'Max', length(signalNames), ...
                'Value', preselectedIndices);

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            defaultName = sprintf('signal_average_%d_signals', length(preselectedSignals));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Show selected count
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 360 20], ...
                'String', sprintf('%d signals pre-selected for averaging', length(preselectedSignals)), ...
                'FontSize', 9, 'ForegroundColor', [0.2 0.6 0.9]);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                selectedIndices = signalListbox.Value;
                if length(selectedIndices) < 2
                    uialert(d, 'Please select at least 2 signals.', 'Invalid Selection');
                    return;
                end

                resultName = strtrim(nameField.String);
                if isempty(resultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                selectedSignals = signalNames(selectedIndices);
                obj.executeSignalAverage(selectedSignals, resultName);
                close(d);
            end
        end

        function showNormDialogWithPreselection(obj, preselectedSignals)
            % Dialog for norm operation with pre-selected signals
            d = dialog('Name', 'Norm Operation', 'Position', [300 300 500 400], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 360 460 25], ...
                'String', 'Compute Norm of Multiple Signals', ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 330 120 20], ...
                'String', 'Selected Signals:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();

            % Find indices of pre-selected signals
            preselectedIndices = [];
            for i = 1:length(preselectedSignals)
                for j = 1:length(signalNames)
                    if strcmp(signalNames{j}, preselectedSignals{i})
                        preselectedIndices(end+1) = j;
                        break;
                    end
                end
            end

            signalListbox = uicontrol('Parent', d, 'Style', 'listbox', ...
                'Position', [150 260 250 70], 'String', signalNames, 'Max', length(signalNames), ...
                'Value', preselectedIndices);

            % Norm type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 220 120 20], ...
                'String', 'Norm Type:', 'FontWeight', 'bold');
            normDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 220 150 25], ...
                'String', {'L1 (Manhattan)', 'L2 (Euclidean)', 'L∞ (Maximum)'}, 'Value', 2);

            % Interpolation options
            interpPanel = uipanel('Parent', d, 'Position', [20 120 460 80], ...
                'Title', 'Time Alignment & Interpolation', 'FontWeight', 'bold');

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 45 120 20], ...
                'String', 'Interpolation:', 'FontWeight', 'bold');
            interpDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 45 150 25], ...
                'String', {'Linear', 'Cubic Spline', 'PCHIP', 'Nearest'}, 'Value', 1);

            uicontrol('Parent', interpPanel, 'Style', 'text', 'Position', [10 15 120 20], ...
                'String', 'Time Range:', 'FontWeight', 'bold');
            rangeDropdown = uicontrol('Parent', interpPanel, 'Style', 'popupmenu', ...
                'Position', [140 15 150 25], ...
                'String', {'Intersection (common)', 'Union (all data)'}, 'Value', 1);

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 80 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            defaultName = sprintf('norm_%d_signals', length(preselectedSignals));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 80 250 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Show selected count
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 50 460 20], ...
                'String', sprintf('%d signals pre-selected for norm calculation', length(preselectedSignals)), ...
                'FontSize', 9, 'ForegroundColor', [0.2 0.6 0.9]);

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [320 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [410 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    selectedIndices = signalListbox.Value;
                    if length(selectedIndices) < 2
                        uialert(d, 'Please select at least 2 signals.', 'Invalid Selection');
                        return;
                    end

                    params = struct();
                    params.SelectedSignals = signalNames(selectedIndices);
                    params.ResultName = strtrim(nameField.String);
                    params.NormType = normDropdown.Value;

                    interpMethods = {'linear', 'spline', 'pchip', 'nearest'};
                    params.InterpolationMethod = interpMethods{interpDropdown.Value};
                    params.TimeRange = rangeDropdown.Value;

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    % Execute operation
                    obj.executeNormOperation(params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end

        function showSimplifiedQuickOperation(obj, operationType, preselectedSignalName)
            % Simplified quick operation dialog
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 400 200], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 160 360 25], ...
                'String', sprintf('%s for Selected Signal', operationType), ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Show selected signal (read-only)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 130 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'text', 'Position', [150 130 230 20], ...
                'String', preselectedSignalName, 'FontWeight', 'normal', ...
                'BackgroundColor', [0.9 0.9 0.9], 'HorizontalAlignment', 'left');

            % Operation-specific parameters
            switch lower(operationType)
                case 'moving average'
                    uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                        'String', 'Window Size:', 'FontWeight', 'bold');
                    paramField = uicontrol('Parent', d, 'Style', 'edit', ...
                        'Position', [150 100 80 25], 'String', '20');

                case 'rms calculation'
                    uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                        'String', 'Window Size:', 'FontWeight', 'bold');
                    paramField = uicontrol('Parent', d, 'Style', 'edit', ...
                        'Position', [150 100 80 25], 'String', '100');

                case 'fft analysis'
                    uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                        'String', 'Output Type:', 'FontWeight', 'bold');
                    paramField = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                        'Position', [150 100 150 25], 'String', {'Magnitude', 'Magnitude (dB)', 'Phase'});
            end

            % Result name - auto-generated
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 70 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanSignalName = obj.extractCleanSignalName(preselectedSignalName);
            switch lower(operationType)
                case 'moving average'
                    defaultName = sprintf('%s_moving_avg', cleanSignalName);
                case 'rms calculation'
                    defaultName = sprintf('%s_rms', cleanSignalName);
                case 'fft analysis'
                    defaultName = sprintf('%s_fft_magnitude', cleanSignalName);
            end

            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 70 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    resultName = strtrim(nameField.String);
                    if isempty(resultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    switch lower(operationType)
                        case 'moving average'
                            windowSize = str2double(paramField.String);
                            if isnan(windowSize) || windowSize < 1
                                uialert(d, 'Please enter a valid window size (>= 1).', 'Invalid Input');
                                return;
                            end
                            obj.executeMovingAverage(preselectedSignalName, windowSize, resultName);

                        case 'rms calculation'
                            windowSize = str2double(paramField.String);
                            if isnan(windowSize) || windowSize < 1
                                uialert(d, 'Please enter a valid window size (>= 1).', 'Invalid Input');
                                return;
                            end
                            obj.executeRMS(preselectedSignalName, windowSize, resultName);

                        case 'fft analysis'
                            outputType = paramField.Value;
                            obj.executeFFT(preselectedSignalName, outputType, resultName);
                    end

                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end
        function cleanName = extractCleanSignalName(obj, signalName)
            % Extract clean signal name from formatted signal name
            % Remove CSV identifiers and format indicators

            cleanName = signalName;

            % Remove "(CSV#: filename)" pattern
            cleanName = regexprep(cleanName, '\s*\(CSV\d+:.*?\)', '');

            % Remove "(Derived)" pattern
            cleanName = strrep(cleanName, ' (Derived)', '');

            % Remove operation icons and spaces
            cleanName = regexprep(cleanName, '^[∂∫−+×÷‖⚡🔄💻]\s*', '');

            % Replace spaces and special characters with underscores for valid variable names
            cleanName = regexprep(cleanName, '[^\w]', '_');

            % Remove multiple consecutive underscores
            cleanName = regexprep(cleanName, '_+', '_');

            % Remove leading/trailing underscores
            cleanName = regexprep(cleanName, '^_+|_+$', '');

            % Ensure it's not empty
            if isempty(cleanName)
                cleanName = 'signal';
            end
        end

        function showQuickFFTWithPreselection(obj, preselectedSignal)
            % Quick dialog for FFT analysis with pre-selected signal
            d = dialog('Name', 'FFT Analysis', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'FFT Analysis', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            preselectedIndex = 1;
            for i = 1:length(signalNames)
                if strcmp(signalNames{i}, preselectedSignal)
                    preselectedIndex = i;
                    break;
                end
            end

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames, 'Value', preselectedIndex);

            % Output type
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Output Type:', 'FontWeight', 'bold');
            typeDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 120 230 25], 'String', {'Magnitude', 'Magnitude (dB)', 'Phase'});

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanSignalName = obj.extractCleanSignalName(preselectedSignal);
            defaultName = sprintf('%s_fft_magnitude', cleanSignalName);
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                outputType = typeDropdown.Value;
                resultName = strtrim(nameField.String);

                if isempty(resultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                obj.executeFFT(signalName, outputType, resultName);
                close(d);
            end
        end

        function showQuickRMSWithPreselection(obj, preselectedSignal)
            % Quick dialog for RMS calculation with pre-selected signal
            d = dialog('Name', 'RMS Calculation', 'Position', [300 300 400 220], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 360 25], ...
                'String', 'Windowed RMS Calculation', ...
                'FontSize', 12, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Signal selection - PRE-POPULATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 150 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');

            signalNames = obj.getAllAvailableSignals();
            preselectedIndex = 1;
            for i = 1:length(signalNames)
                if strcmp(signalNames{i}, preselectedSignal)
                    preselectedIndex = i;
                    break;
                end
            end

            signalDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 150 230 25], 'String', signalNames, 'Value', preselectedIndex);

            % Window size
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 120 120 20], ...
                'String', 'Window Size:', 'FontWeight', 'bold');
            windowField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 120 100 25], 'String', '100', ...
                'HorizontalAlignment', 'left');

            % Result name - AUTO-GENERATED
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 90 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanSignalName = obj.extractCleanSignalName(preselectedSignal);
            defaultName = sprintf('%s_rms', cleanSignalName);
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 90 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Update name when signal changes
            signalDropdown.Callback = @(src, ~) updateName();

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function updateName()
                selectedSignal = signalNames{signalDropdown.Value};
                cleanName = obj.extractCleanSignalName(selectedSignal);
                nameField.String = sprintf('%s_rms', cleanName);
            end

            function computeAndClose()
                signalName = signalNames{signalDropdown.Value};
                windowSize = str2double(windowField.String);
                resultName = strtrim(nameField.String);

                if isnan(windowSize) || windowSize < 1
                    uialert(d, 'Please enter a valid window size (>= 1).', 'Invalid Input');
                    return;
                end

                if isempty(resultName)
                    uialert(d, 'Please enter a result name.', 'Invalid Input');
                    return;
                end

                obj.executeRMS(signalName, windowSize, resultName);
                close(d);
            end
        end

        function confirmDeleteDerivedSignal(obj, signalName)
            % Confirm before deleting a derived signal
            % answer = uiconfirm(obj.App.UIFigure, ...
            %     sprintf('Delete derived signal "%s"?', signalName), ...
            %     'Confirm Delete', 'Options', {'Delete', 'Cancel'}, ...
            %     'DefaultOption', 'Cancel', 'Icon', 'warning');

            % if strcmp(answer, 'Delete')
            obj.deleteDerivedSignal(signalName);
            obj.App.StatusLabel.Text = sprintf('🗑️ Deleted derived signal: %s', signalName);
            obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
            % end
        end
        function success = recalculateDualSignalOperation(obj, signalOps, operation)
            % Recalculate dual signal operations (subtract, add, multiply, divide)
            % This handles interpolation automatically for signals with different time bases

            success = false;

            signalA = operation.InputSignals{1};
            signalB = operation.InputSignals{2};

            [timeA, dataA, ~] = signalOps.getSignalData(signalA);
            [timeB, dataB, ~] = signalOps.getSignalData(signalB);

            if isempty(timeA) || isempty(timeB)
                return; % One or both signals no longer exist
            end

            try
                % CRITICAL: Handle interpolation for different time bases
                % This is where the real magic happens for multi-CSV streaming

                % Check if signals have different time bases
                timeBasesMatch = obj.checkTimeBasesMatch(timeA, timeB);

                if timeBasesMatch
                    % Same time base - no interpolation needed
                    commonTime = timeA;
                    alignedA = dataA;
                    alignedB = dataB;

                    % But still need to handle different lengths due to streaming
                    minLength = min(length(alignedA), length(alignedB));
                    commonTime = commonTime(1:minLength);
                    alignedA = alignedA(1:minLength);
                    alignedB = alignedB(1:minLength);
                else
                    % Different time bases - use saved interpolation parameters
                    [commonTime, alignedA, alignedB] = signalOps.alignTwoSignals(timeA, dataA, timeB, dataB, ...
                        operation.Parameters.InterpolationMethod, operation.Parameters.TimeRange);
                end

                % Perform the operation
                switch operation.Operation
                    case 'subtract'
                        resultData = alignedA - alignedB;
                    case 'add'
                        resultData = alignedA + alignedB;
                    case 'multiply'
                        resultData = alignedA .* alignedB;
                    case 'divide'
                        resultData = alignedA ./ alignedB;
                        % Handle division by zero
                        resultData(~isfinite(resultData)) = NaN;
                    otherwise
                        return;
                end

                % Get the existing derived signal to preserve metadata
                existingDerived = signalOps.DerivedSignals(operation.OutputSignal);

                % Update the derived signal
                derivedSignal = struct();
                derivedSignal.Time = commonTime;
                derivedSignal.Data = resultData;
                derivedSignal.Operation = operation;
                derivedSignal.CreatedAt = existingDerived.CreatedAt;
                derivedSignal.UpdatedAt = datetime('now');

                signalOps.DerivedSignals(operation.OutputSignal) = derivedSignal;
                success = true;

            catch ME
                fprintf('Warning: Failed to recalculate dual signal operation: %s\n', ME.message);
            end
        end

        function success = recalculateNormOperation(obj, signalOps, operation)
            % Recalculate norm operations with proper interpolation handling

            success = false;

            signalData = cell(length(operation.InputSignals), 1);
            timeData = cell(length(operation.InputSignals), 1);

            % Get all signal data
            for i = 1:length(operation.InputSignals)
                [timeData{i}, signalData{i}] = signalOps.getSignalData(operation.InputSignals{i});
                if isempty(timeData{i})
                    return; % One of the signals no longer exists
                end
            end

            try
                % ENHANCED: Smart interpolation handling for multiple signals
                % Check if all signals have compatible time bases
                needsInterpolation = obj.checkIfInterpolationNeeded(timeData);

                if needsInterpolation
                    % Use sophisticated alignment for different time bases
                    [commonTime, alignedData] = signalOps.alignMultipleSignals(timeData, signalData, ...
                        operation.Parameters.InterpolationMethod, operation.Parameters.TimeRange);
                else
                    % All signals have compatible time bases - minimal processing
                    commonTime = timeData{1};  % Use first signal's time base
                    alignedData = zeros(length(commonTime), length(signalData));

                    % Handle different lengths due to streaming
                    minLength = min(cellfun(@length, signalData));
                    commonTime = commonTime(1:minLength);

                    for i = 1:length(signalData)
                        alignedData(:, i) = signalData{i}(1:minLength);
                    end
                    alignedData = alignedData(1:minLength, :);
                end

                % Compute norm
                switch operation.Parameters.NormType
                    case 1  % L1
                        resultData = sum(abs(alignedData), 2);
                    case 2  % L2
                        resultData = sqrt(sum(alignedData.^2, 2));
                    case 3  % L∞
                        resultData = max(abs(alignedData), [], 2);
                    otherwise
                        return;
                end

                % Get the existing derived signal to preserve metadata
                existingDerived = signalOps.DerivedSignals(operation.OutputSignal);

                % Update the derived signal
                derivedSignal = struct();
                derivedSignal.Time = commonTime;
                derivedSignal.Data = resultData;
                derivedSignal.Operation = operation;
                derivedSignal.CreatedAt = existingDerived.CreatedAt;
                derivedSignal.UpdatedAt = datetime('now');

                signalOps.DerivedSignals(operation.OutputSignal) = derivedSignal;
                success = true;

            catch ME
                fprintf('Warning: Failed to recalculate norm operation: %s\n', ME.message);
            end
        end

        function match = checkTimeBasesMatch(~, timeA, timeB)
            % Check if two time vectors have matching time bases (within tolerance)

            if length(timeA) ~= length(timeB)
                match = false;
                return;
            end

            % Check if time vectors are approximately equal
            tolerance = 1e-6;  % Adjust as needed
            timeDiff = abs(timeA - timeB);
            match = all(timeDiff < tolerance);
        end

        function needsInterp = checkIfInterpolationNeeded(obj, timeDataArray)
            % Check if multiple signals need interpolation (different time bases)

            needsInterp = false;

            if length(timeDataArray) < 2
                return;
            end

            % Use first signal as reference
            refTime = timeDataArray{1};

            for i = 2:length(timeDataArray)
                if ~obj.checkTimeBasesMatch(refTime, timeDataArray{i})
                    needsInterp = true;
                    return;
                end
            end
        end

        % Add this method to your SignalOperations class if it doesn't exist
        function derivedSignalNames = getAllDerivedSignalNames(obj)
            % Get all derived signal names from whatever storage mechanism you use
            derivedSignalNames = {};

            try
                % If you store derived signals in a Map or similar structure
                if isprop(obj, 'DerivedSignals') && isa(obj.DerivedSignals, 'containers.Map')
                    derivedSignalNames = keys(obj.DerivedSignals);
                elseif isprop(obj.App.DataManager, 'DerivedSignals') && isa(obj.App.DataManager.DerivedSignals, 'containers.Map')
                    derivedSignalNames = keys(obj.App.DataManager.DerivedSignals);
                end

                % Convert cell array to ensure compatibility
                if ~iscell(derivedSignalNames)
                    derivedSignalNames = {derivedSignalNames};
                end

            catch
                % Return empty if structure doesn't exist or error occurs
                derivedSignalNames = {};
            end
        end
        % Add these missing functions to SignalOperationsManager.m


        function window = createHanningWindow(obj, N)
            % Create Hanning window with fallback for missing Signal Processing Toolbox
            try
                % Try to use the Signal Processing Toolbox function
                window = hann(N);
            catch
                % Create Hanning window manually using the mathematical definition
                % Hanning window: w(n) = 0.5 * (1 - cos(2*pi*n/(N-1)))
                n = 0:N-1;
                window = 0.5 * (1 - cos(2*pi*n/(N-1)))';

                % Optional: Log that we're using manual implementation
                if obj.App.DataManager.IsRunning  % Only log during first use
                    fprintf('Info: Using manual Hanning window (Signal Processing Toolbox not detected)\n');
                end
            end
        end

        function showSimplifiedSingleSignalDialog(obj, operationType, preselectedSignalName)
            % Simplified dialog for single signal operations with fixed signal selection
            d = dialog('Name', sprintf('%s Operation', operationType), ...
                'Position', [300 300 400 250], 'Resize', 'off');

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 210 360 25], ...
                'String', sprintf('Compute %s of Signal', operationType), ...
                'FontSize', 14, 'FontWeight', 'bold', 'HorizontalAlignment', 'center');

            % Show selected signal (read-only)
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 180 120 20], ...
                'String', 'Selected Signal:', 'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'text', 'Position', [150 180 230 20], ...
                'String', preselectedSignalName, 'FontWeight', 'normal', ...
                'BackgroundColor', [0.9 0.9 0.9], 'HorizontalAlignment', 'left');

            % Method selection
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 140 120 20], ...
                'String', 'Method:', 'FontWeight', 'bold');

            switch lower(operationType)
                case 'derivative'
                    methods = {'Gradient (recommended)', 'Forward Difference', 'Backward Difference', 'Central Difference'};
                case 'integral'
                    methods = {'Cumulative Trapezoidal', 'Cumulative Simpson', 'Running Sum'};
                otherwise
                    methods = {'Default'};
            end

            methodDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 140 230 25], 'String', methods, 'Value', 1);

            % Result name - auto-generated
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 100 120 20], ...
                'String', 'Result Name:', 'FontWeight', 'bold');

            cleanSignalName = obj.extractCleanSignalName(preselectedSignalName);
            defaultName = sprintf('%s_%s', cleanSignalName, lower(operationType));
            nameField = uicontrol('Parent', d, 'Style', 'edit', ...
                'Position', [150 100 230 25], 'String', defaultName, ...
                'HorizontalAlignment', 'left');

            % Options (only for operations that need them)
            if strcmp(lower(operationType), 'derivative')
                % Smoothing option
                smoothingCheck = uicontrol('Parent', d, 'Style', 'checkbox', ...
                    'Position', [20 70 200 20], 'String', 'Apply smoothing filter', 'Value', 0);
                windowSizeEdit = uicontrol('Parent', d, 'Style', 'edit', ...
                    'Position', [230 70 50 20], 'String', '5', 'Enable', 'off');

                smoothingCheck.Callback = @(src, ~) set(windowSizeEdit, 'Enable', ...
                    char("on" * src.Value + "off" * (1-src.Value)));
            elseif strcmp(lower(operationType), 'integral')
                % Initial value option
                initialValueCheck = uicontrol('Parent', d, 'Style', 'checkbox', ...
                    'Position', [20 70 200 20], 'String', 'Set initial value', 'Value', 0);
                initialValueEdit = uicontrol('Parent', d, 'Style', 'edit', ...
                    'Position', [230 70 50 20], 'String', '0', 'Enable', 'off');

                initialValueCheck.Callback = @(src, ~) set(initialValueEdit, 'Enable', ...
                    char("on" * src.Value + "off" * (1-src.Value)));
            end

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Compute', ...
                'Position', [220 15 80 30], 'Callback', @(~,~) computeAndClose(), ...
                'FontWeight', 'bold');
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [310 15 80 30], 'Callback', @(~,~) close(d));

            function computeAndClose()
                try
                    params = struct();
                    params.SignalName = preselectedSignalName;
                    params.Method = methods{methodDropdown.Value};
                    params.ResultName = strtrim(nameField.String);

                    % Add operation-specific parameters
                    switch lower(operationType)
                        case 'derivative'
                            if exist('smoothingCheck', 'var')
                                params.ApplySmoothing = smoothingCheck.Value;
                                if params.ApplySmoothing
                                    params.WindowSize = str2double(windowSizeEdit.String);
                                end
                            end
                        case 'integral'
                            if exist('initialValueCheck', 'var')
                                params.SetInitialValue = initialValueCheck.Value;
                                if params.SetInitialValue
                                    params.InitialValue = str2double(initialValueEdit.String);
                                end
                            end
                    end

                    % Validate inputs
                    if isempty(params.ResultName)
                        uialert(d, 'Please enter a result name.', 'Invalid Input');
                        return;
                    end

                    % Execute operation
                    obj.executeSingleSignalOperation(operationType, params);
                    close(d);

                catch ME
                    uialert(d, sprintf('Error: %s', ME.message), 'Operation Failed');
                end
            end
        end
        function exportDerivedSignal(obj, signalName)
            % Export a single derived signal to CSV
            if ~obj.DerivedSignals.isKey(signalName)
                return;
            end

            derivedData = obj.DerivedSignals(signalName);

            % Get save location
            defaultName = sprintf('%s.csv', signalName);
            [file, path] = uiputfile('*.csv', 'Export Derived Signal', defaultName);
            if isequal(file, 0)
                return;
            end

            try
                % Create table and save
                T = table(derivedData.Time, derivedData.Data, 'VariableNames', {'Time', signalName});
                writetable(T, fullfile(path, file));

                obj.App.StatusLabel.Text = sprintf('✅ Exported derived signal: %s', file);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ Export failed: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        %% =================================================================
        %% CLEANUP AND UTILITIES
        %% =================================================================

        function delete(obj)
            % Enhanced cleanup when object is destroyed
            try
                % Clear derived signals map safely
                if ~isempty(obj.DerivedSignals) && isvalid(obj.DerivedSignals)
                    derivedKeys = keys(obj.DerivedSignals);
                    if ~isempty(derivedKeys)
                        remove(obj.DerivedSignals, derivedKeys);
                    end
                end

                % Clear operation history
                obj.OperationHistory = {};

                % Break circular reference to App
                obj.App = [];

            catch ME
                fprintf('Warning during SignalOperationsManager cleanup: %s\n', ME.message);
            end
        end
    end
end