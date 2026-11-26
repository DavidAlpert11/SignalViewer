function sv_export(in, file)
%SV_EXPORT  Save Simulink results as a plain .mat file Signal Viewer reads.
%   Simulink logs to MATLAB objects (Simulink.SimulationData.Dataset - "logsout", SimulationOutput - "out",
%   timeseries, timetable) that only MATLAB can open. This writes each logged signal as a struct with its own time:
%       <name>.time, <name>.values      (multi-rate signals keep their own times)
%
%   sv_export(out, 'run_01.mat')        % the SimulationOutput of sim(...)
%   sv_export(logsout, 'run_01.mat')    % a Dataset
%   sv_export(ts, 'run_01.mat')         % one timeseries (or a cell array of them)
%
%   Then open run_01.mat in Signal Viewer (or signalviewer-cli check run_01.mat --checks requirements.json).

S = struct();
S = add(S, in, '');
if isempty(fieldnames(S))
    error('sv_export:nothing', 'Nothing to save: no logged signals found in the argument.');
end
save(file, '-struct', 'S', '-v7');
fprintf('sv_export: %d signal(s) written to %s\n', numel(fieldnames(S)), file);
end

function S = add(S, x, prefix)
if isa(x, 'Simulink.SimulationOutput')
    for n = x.who'
        S = add(S, x.get(n{1}), n{1});
    end
elseif isa(x, 'Simulink.SimulationData.Dataset')
    for k = 1:x.numElements
        el = x.getElement(k);
        name = el.Name;
        if isempty(name), name = sprintf('signal%d', k); end
        S = add(S, el.Values, join(prefix, name));
    end
elseif isa(x, 'Simulink.SimulationData.Signal') || isa(x, 'Simulink.SimulationData.State')
    S = add(S, x.Values, join(prefix, x.Name));
elseif isa(x, 'timeseries')
    v = squeeze(x.Data);
    if size(v, 1) ~= numel(x.Time), v = v.'; end
    S.(valid(prefix)) = struct('time', double(x.Time(:)), 'values', double(v));
elseif isa(x, 'timetable')
    t = seconds(x.Properties.RowTimes - x.Properties.RowTimes(1));
    for n = x.Properties.VariableNames
        S.(valid(join(prefix, n{1}))) = struct('time', t(:), 'values', double(x.(n{1})));
    end
elseif isstruct(x)                                   % a bus: its elements
    for n = fieldnames(x)'
        S = add(S, x.(n{1}), join(prefix, n{1}));
    end
elseif iscell(x)
    for k = 1:numel(x)
        S = add(S, x{k}, join(prefix, sprintf('e%d', k)));
    end
elseif isnumeric(x) && ~isempty(prefix) && numel(x) > 1
    S.(valid(prefix)) = double(x);                    % tout, a plain vector
end
end

function s = join(a, b)
if isempty(a), s = b; else, s = [a '_' b]; end
end

function s = valid(s)
s = matlab.lang.makeValidName(s);
end
