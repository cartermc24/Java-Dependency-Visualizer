import graphviz as gv
import argparse as ap
import os
from xml.dom import minidom


def select_color(index):
    marker = 9
    ret = index % marker
    return str(ret + 1)


def generate_graph(tree, save_raw=False, inverted=False):
    graph = gv.Digraph(format='png', engine='sfdp')
    graph.graph_attr.update(overlap='false')
    graph.node_attr.update(overlap='false')
    graph.edge_attr.update(overlap='false')

    if inverted:
        graph.graph_attr.update(bgcolor='black')
        graph.node_attr.update(color='white')
        graph.edge_attr.update(bgcolor='white')
        graph.edge_attr.update(fontcolor='white')
        graph.node_attr.update(fontcolor='white')

    subgraphs = {}
    for src_class_id, dst_class_id, obj_id, module in tree:
        if module is not None:
            if module in subgraphs:
                subgraphs[module].edge(str(src_class_id), str(dst_class_id), label=obj_id)
            else:
                print('Generate Graph: New module:', module, 'is assigned color', select_color(len(subgraphs)))
                subgraphs[module] = gv.Digraph(name=module, node_attr={'colorscheme': 'set19',
                                                                       'color': select_color(len(subgraphs))})
                subgraphs[module].edge_attr.update(colorscheme='set19')
                subgraphs[module].edge_attr.update(fontcolor=select_color(len(subgraphs) - 1))
                subgraphs[module].edge_attr.update(color=select_color(len(subgraphs) - 1))
                subgraphs[module].node_attr.update(colorscheme='set19')
                subgraphs[module].node_attr.update(color=select_color(len(subgraphs) - 1))
                subgraphs[module].edge(str(src_class_id), str(dst_class_id), label=obj_id)
        else:
            graph.edge(str(src_class_id), str(dst_class_id), label=obj_id)
    for key in subgraphs.keys():
        graph.subgraph(subgraphs[key])
    if save_raw:
        graph.save(filename="raw.dot")
    file = graph.render(filename="output")
    print("Graph saved as:", file)


def find_independant_classes(tree, threshold=10):
    print("Single-layer independent class dependency search:")
    destination = {}
    for src_class_id, dst_class_id, obj_id, module in tree:
        if dst_class_id in destination:
            destination[dst_class_id] += 1
        else:
            destination[dst_class_id] = 1

    for w in sorted(destination, key=destination.get, reverse=False):
        if destination[w] > threshold:
            break
        print("\t", w, "->", destination[w], "entries")
    pass


def get_interconnection_statistics(tree, num_entries_print=20):
    print("Observed Class Dependency Statistics")
    destination = {}
    source = {}
    for src_class_id, dst_class_id, obj_id, module in tree:
        if src_class_id in source:
            source[src_class_id] += 1
        else:
            source[src_class_id] = 1

        if dst_class_id in destination:
            destination[dst_class_id] += 1
        else:
            destination[dst_class_id] = 1

    index = 0
    print("Top", num_entries_print, "classes that contain the most outbound dependencies:")
    for w in sorted(source, key=source.get, reverse=True):
        if index == num_entries_print:
            break
        print("\t", w, "->", source[w], "entries")
        index += 1

    index = 0
    print("Top", num_entries_print, "classes that are dependencies for other classes:")
    for w in sorted(destination, key=destination.get, reverse=True):
        if index == num_entries_print:
            break
        print("\t", w, "->", destination[w], "entries")
        index += 1


def parse_import_line(line, restriction):
    line = line.replace('import ', '')
    line = line.replace(';', '')
    line = line.strip()
    partition = line.rpartition('.')
    if restriction is None or line.startswith(tuple(restriction)):
        return partition[0], partition[len(partition) - 1]
    else:
        print('\t\t\tIgnoring import:', line, 'as it is outside the scope of the selected class')
        return None, None


def insert_tree(src_classpath, dst_classpath, object, tree, modulename, include_object=False):
    if include_object:
        tree.append((src_classpath, dst_classpath + '.' + object, object))
    else:
        tree.append((src_classpath, dst_classpath, object, modulename))
    # print("!!! File:", src_classpath, " belongs to:", modulename)
    print("\t\t\tFound relationship:", src_classpath, "refers to class", dst_classpath, "[" + object + "]")


def scan_java_source(file, tree, restrictclasses, modulename):
    print('\tScanning Java Source:', file)
    currentclass = None
    with open(file, 'r') as f:
        for line in f:
            if line.startswith('package'):
                currentclass = line.replace('package ', '').replace(';', '').strip() + '.' + \
                               os.path.basename(file).replace('.java', '')
                print('\t\tProcessing class:', currentclass)
            elif line.startswith('import'):
                dst_class, object = parse_import_line(line, restrictclasses)
                if dst_class is not None and object is not None:
                    insert_tree(currentclass, dst_class, object, tree, modulename)


def readpom(file):
    try:
        xmldoc = minidom.parse(file)
        itemlist = xmldoc.getElementsByTagName("project")
        for item in itemlist[0].childNodes:
            if item.localName == 'artifactId':
                return item.firstChild.nodeValue
        return None
    except:
        print("Error: invalid POM - ignoring")
        return None


def build_class_tree(path, tree, ignorefolders, restrictclasses, associatepoms):
    print("Entering folder:", path)
    current_module = None
    for root, dirs, files in os.walk(path):
        for file in files:
            if ignorefolders is not None and any(x in ignorefolders for x in root):
                print("\tIgnoring directory:", root, "as it was chosen to be ignored")
            elif associatepoms and file == 'pom.xml':
                current_module = readpom(os.path.join(root, file))
            elif file.endswith('.java'):
                scan_java_source(os.path.join(root, file), tree, restrictclasses, current_module)
    print("Exiting folder: ", path)
    return tree


if __name__ == "__main__":
    print("Java Class Visualizer /// carter@mccardwell.net")
    parser = ap.ArgumentParser(
        prog='Java Class Visualizer',
        description='Recursively searches and generates a visual connected graph of all Java classes in a director')
    parser.add_argument('--path', metavar='p', type=str, help='The path to the root folder of the Java classes',
                        required=True)
    parser.add_argument('--ignorefolders', metavar='i', type=str,
                        help='Ignores sources in folders with certain names (comma separated)', required=False,
                        default=None)
    parser.add_argument('--restrictclasses', metavar='r', type=str,
                        help='Only analyses classes with the following prefix (comma separated)', required=False,
                        default=None)
    parser.add_argument('--exporttree', metavar='e', type=bool, help='Exports the raw tree to class_tree.txt',
                        required=False, default=False)
    parser.add_argument('--stats', metavar='s', type=int, help='Print the top x classes referenced/depended on',
                        required=False, default=0)
    parser.add_argument('--findindependantclasses', metavar='f', type=bool, default=False,
                        help='Finds classes that have few external dependencies')
    parser.add_argument('--colormavenprojects', metavar='f', type=bool, default=False,
                        help='Colors elements in the graph depending on their Maven module associations')
    parser.add_argument('--invertedcolor', metavar='f', type=bool, default=False,
                        help='Inverts the graph so the background is black and elements are white')
    args = parser.parse_args()

    ignored_folders = None
    restricted_classes = None
    if args.ignorefolders is not None:
        ignored_folders = args.ignorefolders.split(',')
    if args.restrictclasses is not None:
        restricted_classes = args.restrictclasses.split(',')

    class_tree = build_class_tree(args.path, [], ignored_folders, restricted_classes, args.colormavenprojects)
    print("Generating graph, this will take a while for large projects...")
    generate_graph(class_tree, save_raw=args.exporttree, inverted=args.invertedcolor)
    if args.stats > 0:
        get_interconnection_statistics(class_tree, num_entries_print=args.stats)
    if args.findindependantclasses:
        find_independant_classes(class_tree)
